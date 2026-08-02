.PHONY: protos deps run submodule kill

# Variables
PROTO_SOURCE_DIR=helios-protos
PROTO_BUILD_DIR=src/generated

# Find all .proto files in the proto directory and subdirectories
PROTO_SRC := $(shell find $(PROTO_SOURCE_DIR) -name "*.proto")
BETTER_PROTO_PLUGIN=$(shell find .venv -name protoc-gen-python_betterproto2\*)

MKDIR = mkdir -p $(1)
RM = rm -rf
SEPARATOR = /

# Commands
protos:
	$(call RM,$(PROTO_BUILD_DIR))
	$(call MKDIR,$(PROTO_BUILD_DIR))

	protoc \
    --plugin=protoc-gen-python_betterproto2=$(BETTER_PROTO_PLUGIN) \
    -I=$(PROTO_SOURCE_DIR) \
    --python_betterproto2_out=$(PROTO_BUILD_DIR) \
    $(PROTO_SRC)

# Create the directory if it doesn't exist
$(PROTO_BUILD_DIR):
	mkdir -p $(PROTO_BUILD_DIR)

deps:
	uv run sync

run:
	@if [ ! -d "$(PROTO_BUILD_DIR)" ]; then \
		echo "Protobuf build directory not found. Please run 'make proto'"; \
		exit 1; \
	fi

	uv run src/main.py

submodule:
	git submodule update --remote --merge

kill:
	@ids=$$(docker ps -q); \
	if [ -n "$$ids" ]; then \
		docker kill $$ids; \
	else \
		echo "No running containers"; \
	fi