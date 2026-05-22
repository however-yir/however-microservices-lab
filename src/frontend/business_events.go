package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
)

const (
	eventProductViewed        = "product_viewed"
	eventAssistantRecommended = "assistant_recommended"
	eventAddToCart            = "add_to_cart"
	eventCheckoutCompleted    = "checkout_completed"
)

var assistantRecommendationIDPattern = regexp.MustCompile(`\[([A-Za-z0-9_-]{3,64})\]`)

type businessEvent struct {
	EventID           string         `json:"event_id"`
	UserID            string         `json:"user_id"`
	EventType         string         `json:"event_type"`
	EventTime         string         `json:"event_time"`
	Channel           string         `json:"channel"`
	TenantID          string         `json:"tenant_id"`
	SchemaVersion     string         `json:"schema_version"`
	Source            string         `json:"source,omitempty"`
	Route             string         `json:"route,omitempty"`
	ProductID         string         `json:"product_id,omitempty"`
	Quantity          int64          `json:"quantity,omitempty"`
	OrderID           string         `json:"order_id,omitempty"`
	Success           *bool          `json:"success,omitempty"`
	RecommendationIDs []string       `json:"recommendation_ids,omitempty"`
	Confidence        float64        `json:"confidence,omitempty"`
	Metadata          map[string]any `json:"metadata,omitempty"`
}

func (fe *frontendServer) emitBusinessEvent(r *http.Request, eventType string, attrs map[string]any) {
	if strings.TrimSpace(fe.businessEventCollectorURL) == "" {
		return
	}

	event := fe.newBusinessEvent(r, eventType, attrs)
	payload, err := json.Marshal(event)
	if err != nil {
		logBusinessEventError(r, err, "business_event_encode_failed")
		return
	}

	go fe.postBusinessEvent(r.Context(), payload, r)
}

func (fe *frontendServer) newBusinessEvent(r *http.Request, eventType string, attrs map[string]any) businessEvent {
	event := businessEvent{
		EventID:       uuid.NewString(),
		UserID:        sessionID(r),
		EventType:     eventType,
		EventTime:     time.Now().UTC().Format(time.RFC3339Nano),
		Channel:       "web",
		TenantID:      fe.businessEventTenantID,
		SchemaVersion: "v2",
		Route:         routeTemplate(r),
	}

	for key, value := range attrs {
		switch key {
		case "product_id":
			event.ProductID = stringAttr(value)
		case "quantity":
			event.Quantity = intAttr(value)
		case "order_id":
			event.OrderID = stringAttr(value)
		case "success":
			if success, ok := value.(bool); ok {
				event.Success = &success
			}
		case "source":
			event.Source = stringAttr(value)
		case "recommendation_ids":
			if ids, ok := value.([]string); ok {
				event.RecommendationIDs = ids
			}
		case "confidence":
			event.Confidence = floatAttr(value)
		default:
			if event.Metadata == nil {
				event.Metadata = map[string]any{}
			}
			event.Metadata[key] = value
		}
	}

	return event
}

func (fe *frontendServer) postBusinessEvent(parent context.Context, payload []byte, r *http.Request) {
	ctx, cancel := context.WithTimeout(context.WithoutCancel(parent), time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, fe.businessEventCollectorURL, bytes.NewReader(payload))
	if err != nil {
		logBusinessEventError(r, err, "business_event_request_create_failed")
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	client := fe.businessEventClient
	if client == nil {
		client = http.DefaultClient
	}
	res, err := client.Do(req)
	if err != nil {
		logBusinessEventError(r, err, "business_event_send_failed")
		return
	}
	defer res.Body.Close()
	if res.StatusCode >= http.StatusBadRequest {
		logBusinessEventError(r, nil, "business_event_rejected")
	}
}

func extractAssistantRecommendationIDs(message string) []string {
	matches := assistantRecommendationIDPattern.FindAllStringSubmatch(message, -1)
	ids := make([]string, 0, len(matches))
	seen := map[string]bool{}
	for _, match := range matches {
		if len(match) < 2 || seen[match[1]] {
			continue
		}
		ids = append(ids, match[1])
		seen[match[1]] = true
	}
	return ids
}

func logBusinessEventError(r *http.Request, err error, event string) {
	log, ok := r.Context().Value(ctxKeyLog{}).(logrus.FieldLogger)
	if !ok {
		return
	}
	entry := log.WithField("event", event)
	if err != nil {
		entry = entry.WithField("error", err)
	}
	entry.Warn("business event not delivered")
}

func stringAttr(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}

func intAttr(value any) int64 {
	switch typed := value.(type) {
	case int:
		return int64(typed)
	case int32:
		return int64(typed)
	case int64:
		return typed
	case uint64:
		return int64(typed)
	default:
		return 0
	}
}

func floatAttr(value any) float64 {
	switch typed := value.(type) {
	case float32:
		return float64(typed)
	case float64:
		return typed
	default:
		return 0
	}
}
