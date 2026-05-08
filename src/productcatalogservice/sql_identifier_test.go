package main

import "testing"

func TestValidateSQLIdentifier(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		want    string
		wantErr bool
	}{
		{
			name:  "valid whitelisted table name",
			input: "catalog_items",
			want:  "catalog_items",
		},
		{
			name:  "valid another whitelisted name",
			input: "products",
			want:  "products",
		},
		{
			name:    "empty string",
			input:   "",
			wantErr: true,
		},
		{
			name:    "string with spaces",
			input:   "catalog items",
			wantErr: true,
		},
		{
			name:    "string with leading space",
			input:   " catalog_items",
			wantErr: true,
		},
		{
			name:    "string with trailing space",
			input:   "catalog_items ",
			wantErr: true,
		},
		{
			name:    "semicolon injection",
			input:   "catalog_items;DROP TABLE users",
			wantErr: true,
		},
		{
			name:    "single semicolon",
			input:   ";",
			wantErr: true,
		},
		{
			name:    "SQL comment injection",
			input:   "catalog_items--",
			wantErr: true,
		},
		{
			name:    "schema prefix with dot",
			input:   "public.catalog_items",
			wantErr: true,
		},
		{
			name:    "quoted identifier",
			input:   `"catalog_items"`,
			wantErr: true,
		},
		{
			name:    "single quote injection",
			input:   "catalog_items' OR '1'='1",
			wantErr: true,
		},
		{
			name:    "not in whitelist",
			input:   "arbitrary_table",
			wantErr: true,
		},
		{
			name:    "starts with digit",
			input:   "1catalog",
			wantErr: true,
		},
		{
			name:    "starts with hyphen",
			input:   "-catalog",
			wantErr: true,
		},
		{
			name:    "unicode characters",
			input:   "catalog_items_表",
			wantErr: true,
		},
		{
			name:    "newline injection",
			input:   "catalog_items\nDROP TABLE users",
			wantErr: true,
		},
		{
			name:    "tab injection",
			input:   "catalog_items\t",
			wantErr: true,
		},
		{
			name:  "valid underscore prefix",
			input: "cart_sessions",
			want:  "cart_sessions",
		},
		{
			name:  "valid underscore-heavy identifier",
			input: "order_items",
			want:  "order_items",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ValidateSQLIdentifier(tt.input)
			if tt.wantErr {
				if err == nil {
					t.Errorf("ValidateSQLIdentifier(%q) expected error, got nil", tt.input)
				}
				return
			}
			if err != nil {
				t.Errorf("ValidateSQLIdentifier(%q) unexpected error: %v", tt.input, err)
				return
			}
			if got != tt.want {
				t.Errorf("ValidateSQLIdentifier(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestValidTableNamesWhitelist(t *testing.T) {
	// Ensure the whitelist contains the expected entries.
	expected := []string{"catalog_items", "products", "cart_sessions", "orders", "order_items"}
	for _, name := range expected {
		if !validTableNames[name] {
			t.Errorf("expected %q in validTableNames whitelist", name)
		}
	}
}
