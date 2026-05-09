package main

import "testing"

func TestValidateTableName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"valid whitelisted name", "products", false},
		{"valid whitelisted with underscore", "catalog_items", false},
		{"valid whitelisted underscore prefix", "cart_sessions", false},
		{"valid whitelisted with numbers", "order_items", false},
		{"not in whitelist", "product_catalog", true},
		{"empty string", "", true},
		{"space in name", "product catalog", true},
		{"semicolon injection", "products; DROP TABLE users", true},
		{"schema prefix", "public.products", true},
		{"SQL comment", "products--", true},
		{"SQL fragment", "products OR 1=1", true},
		{"quote injection", `products"`, true},
		{"single quote", "products'", true},
		{"dash in name", "product-catalog", true},
		{"number start", "123table", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ValidateSQLIdentifier(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateSQLIdentifier(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}
