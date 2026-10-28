// Command semver sorts the versions given as arguments, oldest first.
package main

import (
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/testifysec/dagger-pushgate-demo/semver"
)

func main() {
	vs := make([]semver.Version, 0, len(os.Args)-1)
	for _, a := range os.Args[1:] {
		v, err := semver.Parse(a)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		vs = append(vs, v)
	}
	sort.SliceStable(vs, func(i, j int) bool { return semver.Compare(vs[i], vs[j]) < 0 })
	for _, v := range vs {
		s := fmt.Sprintf("%d.%d.%d", v.Major, v.Minor, v.Patch)
		if len(v.Pre) > 0 {
			s += "-" + strings.Join(v.Pre, ".")
		}
		fmt.Println(s)
	}
}
