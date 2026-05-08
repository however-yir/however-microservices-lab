package main

import (
	"fmt"
	"regexp"
)

// validSQLIdentifier matches unquoted SQL identifiers: start with letter or underscore,
// followed by letters, digits, or underscores. Max 63 characters (PostgreSQL limit).
var validSQLIdentifier = regexp.MustCompile(`^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`)

// validTableNames is a whitelist of known-safe table names.
// Add entries here when new tables are provisioned.
var validTableNames = map[string]bool{
	"catalog_items":  true,
	"products":       true,
	"cart_sessions":  true,
	"orders":         true,
	"order_items":    true,
}

// ValidateSQLIdentifier checks that name is a safe, unquoted SQL identifier
// that also appears in the whitelist. Returns the validated name or an error.
func ValidateSQLIdentifier(name string) (string, error) {
	if name == "" {
		return "", fmt.Errorf("SQL identifier must not be empty")
	}
	if !validSQLIdentifier.MatchString(name) {
		return "", fmt.Errorf("invalid SQL identifier %q: must match %s", name, validSQLIdentifier.String())
	}
	if !validTableNames[name] {
		return "", fmt.Errorf("table name %q is not in the allowlist", name)
	}
	return name, nil
}
