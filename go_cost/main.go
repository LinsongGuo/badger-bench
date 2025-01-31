package main

import (

	// "crypto/rand"
	"flag"
	"fmt"

	// "math"
	"math/rand"
	"runtime"
	"sync"

	// "runtime/pprof"
	// "runtime/trace"

	"time"

	"github.com/dgraph-io/badger"
	"github.com/dgraph-io/badger/options"
	"github.com/dgraph-io/badger/y"
)

var (
	numGetPtr     = flag.Int("get", 1, "Number of get goroutines.")
	numScanPtr    = flag.Int("scan", 1, "Number of scan goroutines.")
	numKeys       = flag.Float64("keys_mil", 10.0, "How many million keys to write.")
	flagDir       = flag.String("dir", "bench-tmp", "Where data is temporarily stored.")
	flagValueSize = flag.Int("valsz", 128, "Size of each value.")
)

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

const Mf float64 = 1000000
func newKey() []byte {
	k := rand.Int() % int(*numKeys*Mf)
	key := fmt.Sprintf("vsz=%05d-k=%010d", *flagValueSize, k) // 22 bytes.
	return []byte(key)
}

func randomRead(bdb *badger.DB) error {

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

	return bdb.View(func(txn *badger.Txn) error {
		key := newKey()
		//log.Println(key)
		err := readkey(txn, key)
		return err
	})
}

func iterateOnlyKeys(bdb *badger.DB, num int) int {
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
		if count >= num {
			break
		}
	}
	return count
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

const GETCOUNT int = 100000
const SCANCOUNT int = 400

func getLoop(bdb *badger.DB) int {
	// start := time.Now()
	var total int

	for i := 0; i < GETCOUNT; i++ {
		if err := randomRead(bdb); err == nil {
			total++
			// runtime.Gosched()
		}
	}

	// elapsed := time.Since(start)
	// fmt.Printf("getLoop with count=%d took: %v\n", count, elapsed)

	return total
}

func scanLoop(bdb *badger.DB) int {
	var total int
	// start := time.Now()

	for i := 0; i < SCANCOUNT; i++ {
		total += iterateOnlyKeys(bdb, 2000)
	}

	// elapsed := time.Since(start)
	// fmt.Printf("scanLoop with count=%d took: %v\n", count, elapsed)

	return total
}

func main() {

	flag.Parse()
	numGet := *numGetPtr
	numScan := *numScanPtr

	fmt.Println("current GOMAXPROCS:", runtime.GOMAXPROCS(0))

	// initalize badger
	bdb := start_badger()

	// Warmup and measure:
	count := 20000
	start := time.Now()
	for i := 0; i < count; i++ {
		randomRead(bdb)
	}
	elapsed := time.Since(start)
	fmt.Printf("One short takes %.3f us\n", float64(elapsed.Microseconds())/float64(count))

	count = 1000
	var total int
	start = time.Now()
	for i := 0; i < count; i++ {
		total += iterateOnlyKeys(bdb, 2000)
	}
	elapsed = time.Since(start)
	fmt.Printf("One long takes %d us\n", elapsed.Microseconds()/int64(count))
	fmt.Println("Total1 (dummy):", total)

	runtime.GoResetPreemptGen()

	var wg sync.WaitGroup
	start = time.Now()
	// Issue Get goroutines. 
	for i := 0; i < numGet; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			total += getLoop(bdb) // Get the number of successful reads
		}()
	}

	// Issue Scan goroutines. 
	for i := 0; i < numScan; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			total += scanLoop(bdb)
		}()
	}	
	wg.Wait()
	elapsed = time.Since(start)
	
	fmt.Printf("Runtime: %d us\n", elapsed.Microseconds())
	fmt.Println("Total2 (dummy):", total)
}
