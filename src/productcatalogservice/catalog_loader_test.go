package main

import "testing"

func TestValidateTableName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"valid simple name", "products", false},
		{"valid with underscore", "product_catalog", false},
		{"valid starting with underscore", "_hidden", false},
		{"valid with numbers", "table123", false},
		{"valid mixed case", "ProductCatalog", false},
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
		{"null byte", "products\x00", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateTableName(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateTableName(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}
