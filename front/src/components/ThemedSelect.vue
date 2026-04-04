<template>
  <div ref="root" class="themed-select" :class="{ open: isOpen, disabled }">
    <button
      type="button"
      class="themed-select-trigger"
      :class="{ 'is-placeholder': !selectedOption }"
      :disabled="disabled"
      @click="toggleOpen"
    >
      <span class="themed-select-label">{{ selectedOption?.label || placeholder }}</span>
      <span class="themed-select-arrow" aria-hidden="true"></span>
    </button>

  </div>

  <Teleport to="body">
    <transition name="themed-select-pop">
      <div
        v-if="isOpen"
        class="themed-select-menu themed-select-menu-teleported"
        :style="menuStyle"
      >
        <button
          v-for="option in normalizedOptions"
          :key="buildOptionKey(option)"
          type="button"
          class="themed-select-option"
          :class="{ selected: isSelected(option), disabled: option.disabled }"
          :disabled="option.disabled"
          @click="selectOption(option)"
        >
          {{ option.label }}
        </button>
      </div>
    </transition>
  </Teleport>
</template>

<script>
export default {
  name: 'ThemedSelect',
  props: {
    modelValue: {
      type: [String, Number, Boolean, null],
      default: ''
    },
    options: {
      type: Array,
      default: () => []
    },
    placeholder: {
      type: String,
      default: 'Выберите значение'
    },
    disabled: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      isOpen: false,
      menuStyle: {
        top: '0px',
        left: '0px',
        width: '0px'
      }
    }
  },
  computed: {
    normalizedOptions() {
      return this.options.map((option) => {
        if (option && typeof option === 'object' && !Array.isArray(option)) {
          return {
            value: option.value,
            label: option.label ?? String(option.value ?? ''),
            disabled: option.disabled === true
          }
        }

        return {
          value: option,
          label: String(option ?? ''),
          disabled: false
        }
      })
    },
    selectedOption() {
      return this.normalizedOptions.find((option) => this.valuesEqual(option.value, this.modelValue)) || null
    }
  },
  mounted() {
    window.addEventListener('click', this.handleOutsideClick)
    window.addEventListener('keydown', this.handleEscape)
    window.addEventListener('resize', this.updateMenuPosition)
    window.addEventListener('scroll', this.updateMenuPosition, true)
  },
  beforeUnmount() {
    window.removeEventListener('click', this.handleOutsideClick)
    window.removeEventListener('keydown', this.handleEscape)
    window.removeEventListener('resize', this.updateMenuPosition)
    window.removeEventListener('scroll', this.updateMenuPosition, true)
  },
  methods: {
    toggleOpen() {
      if (this.disabled) {
        return
      }

      this.isOpen = !this.isOpen
      if (this.isOpen) {
        this.$nextTick(() => {
          this.updateMenuPosition()
        })
      }
    },
    closeOpen() {
      this.isOpen = false
    },
    selectOption(option) {
      if (option.disabled) {
        return
      }

      this.$emit('update:modelValue', option.value)
      this.$emit('change', option.value)
      this.closeOpen()
    },
    isSelected(option) {
      return this.valuesEqual(option.value, this.modelValue)
    },
    buildOptionKey(option) {
      return `${typeof option.value}-${String(option.value)}-${option.label}`
    },
    valuesEqual(left, right) {
      if (left === right) {
        return true
      }

      if (left === '' || right === '' || left === null || right === null || left === undefined || right === undefined) {
        return false
      }

      return String(left) === String(right)
    },
    handleOutsideClick(event) {
      if (!this.isOpen) {
        return
      }

      if (!this.$refs.root?.contains(event.target)) {
        this.closeOpen()
      }
    },
    handleEscape(event) {
      if (event.key === 'Escape') {
        this.closeOpen()
      }
    },
    updateMenuPosition() {
      if (!this.isOpen || !this.$refs.root) {
        return
      }

      const rect = this.$refs.root.getBoundingClientRect()
      this.menuStyle = {
        top: `${rect.bottom + 10}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`
      }
    }
  }
}
</script>

<style scoped>
.themed-select {
  position: relative;
  width: 100%;
}

.themed-select-trigger {
  width: 100%;
  min-height: 48px;
  border: 1px solid rgba(125, 169, 255, 0.28);
  border-radius: 20px;
  padding: 0 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.11), rgba(255, 255, 255, 0.07)),
    rgba(13, 24, 88, 0.94);
  color: #f2f6ff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.18s ease;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.themed-select-trigger:hover {
  border-color: rgba(153, 188, 255, 0.46);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    0 12px 24px rgba(5, 12, 44, 0.16);
}

.themed-select.open .themed-select-trigger {
  border-color: rgba(125, 169, 255, 0.72);
  box-shadow:
    0 0 0 1px rgba(125, 169, 255, 0.32),
    0 12px 28px rgba(5, 12, 44, 0.2);
}

.themed-select.disabled .themed-select-trigger {
  opacity: 0.72;
  cursor: not-allowed;
}

.themed-select-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
}

.themed-select-trigger.is-placeholder .themed-select-label {
  color: rgba(231, 239, 255, 0.72);
}

.themed-select-arrow {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border-right: 2px solid rgba(231, 239, 255, 0.92);
  border-bottom: 2px solid rgba(231, 239, 255, 0.92);
  transform: rotate(45deg) translateY(-2px);
  transition: transform 0.2s ease;
}

.themed-select.open .themed-select-arrow {
  transform: rotate(-135deg) translateX(-1px);
}

.themed-select-menu {
  z-index: 120;
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 22px;
  border: 1px solid rgba(125, 169, 255, 0.2);
  background:
    linear-gradient(180deg, rgba(12, 20, 76, 0.98), rgba(8, 13, 52, 0.98));
  box-shadow: 0 24px 50px rgba(0, 0, 0, 0.34);
  max-height: 240px;
  overflow-y: auto;
}

.themed-select-menu-teleported {
  position: fixed;
}

.themed-select-option {
  width: 100%;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: 16px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.04);
  color: #f2f6ff;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.themed-select-option:hover {
  background: rgba(93, 130, 255, 0.18);
  border-color: rgba(125, 169, 255, 0.22);
  transform: translateY(-1px);
}

.themed-select-option.selected {
  background: linear-gradient(135deg, rgba(70, 118, 255, 0.72), rgba(55, 95, 224, 0.76));
  border-color: rgba(167, 195, 255, 0.36);
}

.themed-select-option.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.themed-select-pop-enter-active,
.themed-select-pop-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.themed-select-pop-enter-from,
.themed-select-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
