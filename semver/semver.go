// Package semver parses and orders Semantic Versioning 2.0.0 versions.
package semver

import (
	"fmt"
	"strconv"
	"strings"
)

// Version is a parsed semantic version. Build metadata is kept but never
// affects ordering, per the spec.
type Version struct {
	Major, Minor, Patch uint64
	Pre                 []string
	Build               string
}

// Parse reads "1.2.3", "v1.2.3", "1.2.3-rc.1" or "1.2.3+build.5".
func Parse(s string) (Version, error) {
	var v Version
	in := strings.TrimPrefix(s, "v")
	if i := strings.IndexByte(in, '+'); i >= 0 {
		v.Build = in[i+1:]
		if v.Build == "" {
			return Version{}, fmt.Errorf("semver %q: empty build metadata", s)
		}
		in = in[:i]
	}
	if i := strings.IndexByte(in, '-'); i >= 0 {
		pre := in[i+1:]
		in = in[:i]
		if pre == "" {
			return Version{}, fmt.Errorf("semver %q: empty pre-release", s)
		}
		for _, id := range strings.Split(pre, ".") {
			if id == "" {
				return Version{}, fmt.Errorf("semver %q: empty pre-release identifier", s)
			}
			if isNum(id) && len(id) > 1 && id[0] == '0' {
				return Version{}, fmt.Errorf("semver %q: leading zero in %q", s, id)
			}
			v.Pre = append(v.Pre, id)
		}
	}
	parts := strings.Split(in, ".")
	if len(parts) != 3 {
		return Version{}, fmt.Errorf("semver %q: want MAJOR.MINOR.PATCH", s)
	}
	nums := [3]*uint64{&v.Major, &v.Minor, &v.Patch}
	for i, p := range parts {
		if !isNum(p) || (len(p) > 1 && p[0] == '0') {
			return Version{}, fmt.Errorf("semver %q: bad number %q", s, p)
		}
		n, err := strconv.ParseUint(p, 10, 64)
		if err != nil {
			return Version{}, fmt.Errorf("semver %q: %w", s, err)
		}
		*nums[i] = n
	}
	return v, nil
}

// Compare returns -1, 0 or 1. A pre-release sorts before its release.
func Compare(a, b Version) int {
	for _, d := range [][2]uint64{{a.Major, b.Major}, {a.Minor, b.Minor}, {a.Patch, b.Patch}} {
		if d[0] != d[1] {
			if d[0] < d[1] {
				return -1
			}
			return 1
		}
	}
	switch {
	case len(a.Pre) == 0 && len(b.Pre) == 0:
		return 0
	case len(a.Pre) == 0:
		return 1
	case len(b.Pre) == 0:
		return -1
	}
	for i := 0; i < len(a.Pre) && i < len(b.Pre); i++ {
		if c := compareIdent(a.Pre[i], b.Pre[i]); c != 0 {
			return c
		}
	}
	switch {
	case len(a.Pre) < len(b.Pre):
		return -1
	case len(a.Pre) > len(b.Pre):
		return 1
	}
	return 0
}

func compareIdent(a, b string) int {
	an, bn := isNum(a), isNum(b)
	switch {
	case an && bn:
		if len(a) != len(b) {
			if len(a) < len(b) {
				return -1
			}
			return 1
		}
		return strings.Compare(a, b)
	case an:
		return -1
	case bn:
		return 1
	}
	return strings.Compare(a, b)
}

func isNum(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}
