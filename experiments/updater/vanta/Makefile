# Vanta 0.1 has no imports, so each runnable program is its entry file with
# src/guard.vanta appended. `vanta run` then executes the joined file.

BUILD := build

.PHONY: all clean

all: $(BUILD)/main.vanta $(BUILD)/main_test.vanta

$(BUILD):
	mkdir -p $@

$(BUILD)/main.vanta: src/main.vanta src/guard.vanta | $(BUILD)
	cat $^ > $@

$(BUILD)/main_test.vanta: tests/main_test.vanta src/guard.vanta | $(BUILD)
	cat $^ > $@

clean:
	rm -rf $(BUILD)
