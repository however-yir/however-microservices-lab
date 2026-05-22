package main

import (
	"context"
	"net/http/httptest"
	"reflect"
	"testing"
)

func TestExtractAssistantRecommendationIDs(t *testing.T) {
	got := extractAssistantRecommendationIDs("try [ABC123], [ABC123], and [sku-789]")
	want := []string{"ABC123", "sku-789"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("extractAssistantRecommendationIDs() = %v, want %v", got, want)
	}
}

func TestNewBusinessEventDefaults(t *testing.T) {
	req := httptest.NewRequest("GET", "/product/ABC123?source=assistant", nil)
	req = req.WithContext(context.WithValue(req.Context(), ctxKeySessionID{}, "session-1"))
	fe := &frontendServer{businessEventTenantID: "tenant_demo"}

	event := fe.newBusinessEvent(req, eventProductViewed, map[string]any{
		"product_id": "ABC123",
		"source":     "assistant",
	})

	if event.EventType != eventProductViewed {
		t.Fatalf("event type = %q, want %q", event.EventType, eventProductViewed)
	}
	if event.UserID != "session-1" {
		t.Fatalf("user id = %q, want session-1", event.UserID)
	}
	if event.Channel != "web" || event.TenantID != "tenant_demo" || event.SchemaVersion != "v2" {
		t.Fatalf("unexpected defaults: %+v", event)
	}
	if event.ProductID != "ABC123" || event.Source != "assistant" {
		t.Fatalf("unexpected product attrs: %+v", event)
	}
}
