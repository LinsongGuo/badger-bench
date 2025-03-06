# Makefile for building the BadgerDB server using Aspen-Go.
# 
# Prerequisites:
# 1. Navigate to the Aspen-Go source directory: `cd aspen-go/go/src`
# 2. Run `./make.bash` to ensure the Aspen-Go binary is built.
#
# This Makefile assumes that the Aspen-Go binary is located at `../../go/bin/go` 
# relative to the directory containing this Makefile.

# Define paths
MAKEPATH := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ASPENGO := $(MAKEPATH)/../../go/bin/go
BINARY := badger-server

all: build

# Build the BadgerDB server
build:
	$(ASPENGO) build -o $(BINARY)

clean:
	rm -f $(BINARY)

.PHONY: all build clean
