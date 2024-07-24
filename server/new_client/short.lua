-- Desc: Send a distribution of all short 100 us requests
-- average duration: 100 us
-- ideal: 10,000 requests/core/s
math.randomseed(os.time())

request_short = function()
    headers = {}
    headers["Content-Type"] = "application/json"
    body = '{"name":"short"}'
    return wrk.format("GET", "/getkey/1", headers, body)
end

request = function()
    return request_short()
end

done = function(summary, latency, requests)
    print("all done!\n")

    -- 50% of 95% (approx p50 of short requests)
    print(string.format(" 47.500%%  %.2fus", latency:percentile(47.5)))

    -- 99% of 95% (approx p99 of short requests)
    print(string.format(" 94.050%%  %.2fus", latency:percentile(94.05)))

    -- 95% + 99% of 5% (approx p99 of long requests)
    print(string.format(" 99.950%%  %.2fus", latency:percentile(99.95)))
end