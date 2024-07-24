-- Desc: Send a bimodal distribution of requests
-- 95% 1 us, 5% 260 us
-- average duration: 13.95 us
-- ideal: 71,684 requests/core/s
math.randomseed(os.time())

request_short = function()
    headers = {}
    headers["Content-Type"] = "application/json"
    body = '{"name":"short"}'
    return wrk.format("GET", "/getkey/1", headers, body)
end

request_long = function()
    headers = {}
    headers["Content-Type"] = "application/json"
    body = '{"name":"long"}'
    return wrk.format("GET", "/iteratekey/1", headers, body)
end

request = function()
    if math.random(1, 100) <= 95 then
        return request_short()
    else
        return request_long()
    end
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