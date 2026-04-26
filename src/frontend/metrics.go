package main

import (
	"fmt"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
)

type frontendMetricKey struct {
	Method string
	Route  string
	Status string
}

type frontendDurationKey struct {
	Method string
	Route  string
}

var frontendMetrics = struct {
	sync.Mutex
	Requests    map[frontendMetricKey]int64
	DurationSum map[frontendDurationKey]float64
	DurationCnt map[frontendDurationKey]int64
}{
	Requests:    map[frontendMetricKey]int64{},
	DurationSum: map[frontendDurationKey]float64{},
	DurationCnt: map[frontendDurationKey]int64{},
}

func metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rr := &responseRecorder{w: w}
		next.ServeHTTP(rr, r)
		if rr.status == 0 {
			rr.status = http.StatusOK
		}

		route := routeTemplate(r)
		requestKey := frontendMetricKey{
			Method: r.Method,
			Route:  route,
			Status: strconv.Itoa(rr.status),
		}
		durationKey := frontendDurationKey{
			Method: r.Method,
			Route:  route,
		}

		frontendMetrics.Lock()
		defer frontendMetrics.Unlock()
		frontendMetrics.Requests[requestKey]++
		frontendMetrics.DurationSum[durationKey] += time.Since(start).Seconds()
		frontendMetrics.DurationCnt[durationKey]++
	})
}

func routeTemplate(r *http.Request) string {
	route := mux.CurrentRoute(r)
	if route == nil {
		return "unmatched"
	}
	template, err := route.GetPathTemplate()
	if err != nil || template == "" {
		return "unmatched"
	}
	return template
}

func frontendMetricsHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")

	frontendMetrics.Lock()
	defer frontendMetrics.Unlock()

	requestKeys := make([]frontendMetricKey, 0, len(frontendMetrics.Requests))
	for key := range frontendMetrics.Requests {
		requestKeys = append(requestKeys, key)
	}
	sort.Slice(requestKeys, func(i, j int) bool {
		return requestKeys[i].Method+requestKeys[i].Route+requestKeys[i].Status <
			requestKeys[j].Method+requestKeys[j].Route+requestKeys[j].Status
	})

	fmt.Fprintln(w, "# HELP frontend_http_requests_total Total frontend HTTP requests.")
	fmt.Fprintln(w, "# TYPE frontend_http_requests_total counter")
	for _, key := range requestKeys {
		fmt.Fprintf(
			w,
			"frontend_http_requests_total{method=%q,route=%q,status=%q} %d\n",
			escapeMetricLabel(key.Method),
			escapeMetricLabel(key.Route),
			escapeMetricLabel(key.Status),
			frontendMetrics.Requests[key],
		)
	}

	durationKeys := make([]frontendDurationKey, 0, len(frontendMetrics.DurationSum))
	for key := range frontendMetrics.DurationSum {
		durationKeys = append(durationKeys, key)
	}
	sort.Slice(durationKeys, func(i, j int) bool {
		return durationKeys[i].Method+durationKeys[i].Route <
			durationKeys[j].Method+durationKeys[j].Route
	})

	fmt.Fprintln(w, "# HELP frontend_http_request_duration_seconds Frontend HTTP request duration.")
	fmt.Fprintln(w, "# TYPE frontend_http_request_duration_seconds summary")
	for _, key := range durationKeys {
		fmt.Fprintf(
			w,
			"frontend_http_request_duration_seconds_sum{method=%q,route=%q} %.6f\n",
			escapeMetricLabel(key.Method),
			escapeMetricLabel(key.Route),
			frontendMetrics.DurationSum[key],
		)
		fmt.Fprintf(
			w,
			"frontend_http_request_duration_seconds_count{method=%q,route=%q} %d\n",
			escapeMetricLabel(key.Method),
			escapeMetricLabel(key.Route),
			frontendMetrics.DurationCnt[key],
		)
	}
}

func escapeMetricLabel(value string) string {
	value = strings.ReplaceAll(value, "\\", "\\\\")
	value = strings.ReplaceAll(value, "\n", "\\n")
	return strings.ReplaceAll(value, "\"", "\\\"")
}
