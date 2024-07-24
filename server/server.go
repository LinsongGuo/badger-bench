package main

import (
	"context"
	// "crypto/rand"
	"flag"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"

	// "math"
	"math/rand"
	"os"
	"os/signal"
	"runtime"
  "runtime/pprof"
	"runtime/trace"

	// "runtime/pprof"
	// "runtime/trace"
	"strconv"
	"syscall"
	"time"

	"github.com/dgraph-io/badger"
	"github.com/dgraph-io/badger/options"
	"github.com/dgraph-io/badger/y"

	"github.com/gofiber/fiber/v3"
)

const Mi int = 1000000
const Mf float64 = 1000000

var (
	ctx           = context.Background()
	numKeys       = flag.Float64("keys_mil", 10.0, "How many million keys to write.")
	flagDir       = flag.String("dir", "bench-tmp", "Where data is temporarily stored.")
	flagValueSize = flag.Int("valsz", 128, "Size of each value.")
	run_ptr       = flag.String("run", "", "name of run")
	port_ptr      = flag.Int("port", 3001, "port number to listen on")
	trace_ptr     = flag.Bool("trace", false, "collect execution traces")
)

func trace_runner(run string, port int) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGUSR1, syscall.SIGUSR2)
	var trace_num int = 0
	var f_trace *os.File = nil
	var f_cpu_prof *os.File = nil
	var tracing bool = false

	for {
		sig := <-sigChan

		if sig == syscall.SIGUSR1 {
			// try to start collecting a trace

			if tracing {
				// currently collecting a trace, stop it first
				trace.Stop()
				f_trace.Close()

				// stop the CPU profile
				pprof.StopCPUProfile()
				f_cpu_prof.Close()
				tracing = false
			}

			// start collecting a trace
			tracefile := fmt.Sprintf("%s/trace_%d_%d", run, port, trace_num) // todo: remove trace_num?
			f_trace, err := os.Create(tracefile)
			if err != nil {
				panic(err)
			}
			err = trace.Start(f_trace)
			if err != nil {
				panic(err)
			}

			// also start collecting a CPU profile
			cpu_prof_filename := fmt.Sprintf("%s/cpu_%d_%d.prof", run, port, trace_num)
			trace_num += 1
			f_cpu_prof, err := os.Create(cpu_prof_filename)
			if err != nil {
				panic(err)
			}
			err = pprof.StartCPUProfile(f_cpu_prof)
			if err != nil {
				panic(err)
			}

			tracing = true
		} else if sig == syscall.SIGUSR2 {
			// stop collecting the trace and CPU profile
			if tracing {
				trace.Stop()
				f_trace.Close()

				pprof.StopCPUProfile()
				f_cpu_prof.Close()
				tracing = false
			}
		}
	}
}

// Badger hit counter
type hitCounter struct {
	found    uint64
	notFound uint64
	errored  uint64
}

func (h *hitCounter) Reset() {
	h.found, h.notFound, h.errored = 0, 0, 0
}

func (h *hitCounter) Update(c *hitCounter) {
	atomic.AddUint64(&h.found, c.found)
	atomic.AddUint64(&h.notFound, c.notFound)
	atomic.AddUint64(&h.errored, c.errored)
}

func (h *hitCounter) Print(storeName string, b *testing.B) {
	b.Logf("%s: %d keys had valid values.", storeName, h.found)
	b.Logf("%s: %d keys had no values", storeName, h.notFound)
	b.Logf("%s: %d keys had errors", storeName, h.errored)
	b.Logf("%s: %d total keys looked at", storeName, h.found+h.notFound+h.errored)
	b.Logf("%s: hit rate : %.2f", storeName, float64(h.found)/float64(h.found+h.notFound+h.errored))
}

// Badger utility functions
func safecopy(dst []byte, src []byte) []byte {
	if cap(dst) < len(src) {
		dst = make([]byte, len(src))
	}
	dst = dst[0:len(src)]
	copy(dst, src)
	return dst
}

func getBadger() (*badger.DB, error) {
	opt := badger.DefaultOptions(*flagDir + "/badger")
	opt.TableLoadingMode = options.LoadToRAM
	opt.ReadOnly = true
	return badger.Open(opt)
}

func newKey() []byte {
	k := rand.Int() % int(*numKeys*Mf)
	key := fmt.Sprintf("vsz=%05d-k=%010d", *flagValueSize, k) // 22 bytes.
	//log.Println(key)
	return []byte(key)
}

func randomRead(bdb *badger.DB) {

	readkey := func(txn *badger.Txn, key []byte) error {
		item, err := txn.Get(key)
		if err != nil {
			return err
		}
		val, err := item.ValueCopy(nil)
		if err != nil {
			return err
		}
		y.AssertTruef(len(val) == *flagValueSize,
			"Assertion failed. value size is %d, expected %d", len(val), *flagValueSize)
		return nil
	}

	_ = bdb.View(func(txn *badger.Txn) error {
		key := newKey()
		//log.Println(key)
		err := readkey(txn, key)
		return err
	})

	// y.Check(err)
	//if err != nil {
	//	fmt.Println("error")
	//}
}

func iterateOnlyKeys(bdb *badger.DB, num int) int64 {
	iterateOnce := func(n int) {
		k := make([]byte, 1024)
		var count int
		opt := badger.IteratorOptions{}
		opt.PrefetchSize = 256
		txn := bdb.NewTransaction(false)
		itr := txn.NewIterator(opt)
		for itr.Rewind(); itr.Valid(); itr.Next() {
			item := itr.Item()
			{
				k = safecopy(k, item.Key())
			}
			count++
			if count >= n {
				break
			}
		}
	}

	start := time.Now()
	iterateOnce(num)
	elapsed := time.Since(start)
	// fmt.Printf("Execution time: %d µs\n", elapsed.Microseconds())
	return elapsed.Microseconds()
}

func shutdown(app *fiber.App, bdb *badger.DB, start_time time.Time) {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM)

	// wait for a signal
	<-sigChan

	fmt.Printf("shutting down app after executing for %.2f seconds\n",
		time.Since(start_time).Seconds())
	_ = app.Shutdown()
	bdb.Close()
}

func start_badger() *badger.DB {
	bdb, err := getBadger()
	y.Check(err)

	//all_keys(bdb)

	return bdb
}

func all_keys(bdb *badger.DB) error {
	err := bdb.View(func(txn *badger.Txn) error {
		opts := badger.DefaultIteratorOptions
		opts.PrefetchSize = 10
		opts.PrefetchValues = false
		it := txn.NewIterator(opts)
		defer it.Close()
		for it.Rewind(); it.Valid(); it.Next() {
			k := it.Item().Key()
			fmt.Printf("key=%s\n", k)
		}
		return nil
	})
	return err
}

func main() {
	start_time := time.Now()

	flag.Parse()
	run := *run_ptr
	port := *port_ptr
	trace := *trace_ptr
	fmt.Println("current GOMAXPROCS:", runtime.GOMAXPROCS(0))

	// initalize badger
	bdb := start_badger()

  // start a goroutine to collect traces
	if trace {
    runtime.GOMAXPROCS(runtime.GOMAXPROCS(0) + 1)
		go trace_runner(run, port)
	}
	// initialize server
	app := fiber.New()

	fmt.Println("App started")

	// start a goroutine to shutdown gracefully
	go shutdown(app, bdb, start_time)

	app.Get("/getkey/:num", func(c fiber.Ctx) error {
		//fmt.Println("received getkey request")
		num := fiber.Params[int](c, "num")

		// do num randomReads
		var wg sync.WaitGroup
		wg.Add(num)

		start := time.Now()
		for i := 0; i < num; i++ {
			go func() {
				defer wg.Done()
				randomRead(bdb)
			}()
		}
		elapsed := time.Since(start)

		wg.Wait()

		return c.SendString(strconv.Itoa(int(elapsed.Microseconds())))
	})

	app.Get("/iteratekey/:num/:count", func(c fiber.Ctx) error {
		num := fiber.Params[int](c, "num")
		count := fiber.Params[int](c, "count")

		// do num randomReads
		var wg sync.WaitGroup

		total := int64(0)
		wg.Add(count)

		for i := 0; i < count; i++ {
			go func() {
				defer wg.Done()
				total += iterateOnlyKeys(bdb, num)
			}()
		}

		wg.Wait()

		return c.SendString(strconv.Itoa(int(total / int64(count))))
	})

	err := app.Listen(":" + strconv.Itoa(port))
	if err != nil {
		fmt.Println("Error starting server:", err)
	}
}
