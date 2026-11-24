package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/v2fly/v2ray-core/v5/app/router/routercommon"
	"google.golang.org/protobuf/proto"
)

type domainKey struct {
	kind  routercommon.Domain_Type
	value string
}

func covered(domain *routercommon.Domain, rules map[domainKey]bool) bool {
	kind, value := domain.GetType(), domain.GetValue()
	if rules[domainKey{kind, value}] {
		return true
	}
	if kind != routercommon.Domain_Full && kind != routercommon.Domain_RootDomain {
		return false
	}
	for {
		if rules[domainKey{routercommon.Domain_RootDomain, value}] {
			return true
		}
		_, parent, found := strings.Cut(value, ".")
		if !found {
			return false
		}
		value = parent
	}
}

func verify(file, reportPath string) error {
	raw, err := os.ReadFile(file)
	if err != nil {
		return err
	}
	if len(raw) == 0 || len(raw) > 100*1024*1024 {
		return fmt.Errorf("block-list.dat is empty or exceeds the 100 MiB Git limit")
	}
	var data routercommon.GeoSiteList
	if err := proto.Unmarshal(raw, &data); err != nil {
		return err
	}
	tags := make(map[string][]*routercommon.Domain)
	for _, entry := range data.GetEntry() {
		tag := strings.ToUpper(entry.GetCountryCode())
		if _, exists := tags[tag]; tag == "" || tag == "ALL" || exists {
			return fmt.Errorf("unexpected or duplicate block-list tag %q", tag)
		}
		tags[tag] = entry.GetDomain()
	}
	bank := make(map[domainKey]bool)
	for _, domain := range tags["CATEGORY-BANK"] {
		bank[domainKey{domain.GetType(), domain.GetValue()}] = true
	}
	if len(bank) == 0 || len(tags["CATEGORY-BANK-LEGACY"]) == 0 {
		return fmt.Errorf("missing bank aggregate or legacy bank rules")
	}
	for tag, domains := range tags {
		if !strings.HasPrefix(tag, "CATEGORY-BANK-") {
			continue
		}
		for _, domain := range domains {
			if !covered(domain, bank) {
				return fmt.Errorf("category-bank lacks %s from %s", domain.GetValue(), tag)
			}
		}
	}

	reportBytes, err := os.ReadFile(reportPath)
	if err != nil {
		return err
	}
	var report struct {
		Sources map[string]struct {
			Tags map[string]string `json:"tags"`
		} `json:"sources"`
	}
	if err := json.Unmarshal(reportBytes, &report); err != nil {
		return err
	}
	for name, source := range report.Sources {
		for _, reference := range source.Tags {
			tag, ok := strings.CutPrefix(reference, "ext:block-list.dat:")
			if !ok || len(tags[strings.ToUpper(tag)]) == 0 {
				return fmt.Errorf("%s references missing block-list tag %q", name, reference)
			}
		}
	}
	fmt.Printf("Verified block-list.dat with %d tags and %d aggregate bank rules\n", len(tags), len(bank))
	return nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: verify_dat BLOCK_LIST REPORT")
		os.Exit(2)
	}
	if err := verify(os.Args[1], os.Args[2]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
