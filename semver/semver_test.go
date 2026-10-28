package semver

import (
	"sort"
	"testing"
)

func TestParse(t *testing.T) {
	v, err := Parse("v1.20.3-rc.1+build.7")
	if err != nil {
		t.Fatal(err)
	}
	if v.Major != 1 || v.Minor != 20 || v.Patch != 3 || len(v.Pre) != 2 || v.Build != "build.7" {
		t.Fatalf("got %+v", v)
	}
}

func TestParseRejects(t *testing.T) {
	for _, s := range []string{"1.2", "1.2.3.4", "01.2.3", "1.2.3-", "1.2.3-01", "1.2.3+", "1..3", "a.b.c", "1.2.3-rc..1"} {
		if _, err := Parse(s); err == nil {
			t.Errorf("Parse(%q) accepted", s)
		}
	}
}

// The precedence example from semver.org section 11, sorted from reversed order.
func TestSpecOrdering(t *testing.T) {
	want := []string{
		"1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
		"1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0",
	}
	got := make([]string, len(want))
	for i := range want {
		got[i] = want[len(want)-1-i]
	}
	sort.Slice(got, func(i, j int) bool { return Compare(mustParse(t, got[i]), mustParse(t, got[j])) < 0 })
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("position %d: got %s, want %s (full: %v)", i, got[i], want[i], got)
		}
	}
}

func TestBuildMetadataIgnored(t *testing.T) {
	if c := Compare(mustParse(t, "1.0.0+a"), mustParse(t, "1.0.0+b")); c != 0 {
		t.Fatalf("Compare = %d, want 0", c)
	}
}

func TestNumericBeforeAlphanumeric(t *testing.T) {
	if c := Compare(mustParse(t, "1.0.0-9"), mustParse(t, "1.0.0-a")); c != -1 {
		t.Fatalf("Compare = %d, want -1", c)
	}
}

func TestMajorDominates(t *testing.T) {
	if c := Compare(mustParse(t, "2.0.0"), mustParse(t, "1.99.99")); c != 1 {
		t.Fatalf("Compare = %d, want 1", c)
	}
}

func mustParse(t *testing.T, s string) Version {
	t.Helper()
	v, err := Parse(s)
	if err != nil {
		t.Fatal(err)
	}
	return v
}

func TestPatchOrdering(t *testing.T) {
	if c := Compare(mustParse(t, "1.2.10"), mustParse(t, "1.2.9")); c != 1 {
		t.Fatalf("Compare = %d, want 1 (numeric, not lexical)", c)
	}
}

func TestPrereleaseBeforeRelease(t *testing.T) {
	if c := Compare(mustParse(t, "2.0.0-rc.1"), mustParse(t, "2.0.0")); c != -1 {
		t.Fatalf("Compare = %d, want -1", c)
	}
}
