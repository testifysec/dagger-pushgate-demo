package semver

import (
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
)

// TestSuiteLoad stands in for the rest of a real test suite. It parses and
// compares versions for the number of seconds in testdata/suite-seconds, so
// the benchmark workflows can model a 5, 30 or 60 minute suite with the same
// code. The file is committed, so changing it changes the inputs Dagger and
// Go cache on.
func TestSuiteLoad(t *testing.T) {
	raw, err := os.ReadFile("../testdata/suite-seconds")
	if err != nil {
		t.Fatal(err)
	}
	secs, err := strconv.Atoi(strings.TrimSpace(string(raw)))
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(time.Duration(secs) * time.Second)
	n := 0
	for time.Now().Before(deadline) {
		a, _ := Parse("1.0.0-beta.11")
		b, _ := Parse("1.0.0-rc.1")
		if Compare(a, b) != -1 {
			t.Fatal("ordering changed under load")
		}
		n++
	}
	t.Logf("%d comparisons in %ds", n, secs)
}
