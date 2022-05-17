<template>
  <div>
    <input type="text"
           v-model="internalValue"
           :disabled="disabled"
           @focus="makeFocused(true)"
           @blur="makeFocused(false)"
           @input="updateValue()"
           v-on:keydown.up.capture.prevent="arrowKey(-1)"
           v-on:keydown.down.capture.prevent="arrowKey(1)"
           v-on:keydown.enter.capture.prevent="enterKey()">
    <div class="suggestion-list-wrapper"
         @mouseover="isMouseInside = true"
         @mouseleave="isMouseInside = false">
      <div class="elevation-3 suggestion-list">
        <div v-for="(item, index) in visibleItems"
             :key="index"
             class="suggestion-item"
             @click="select(item)"
             @mouseover="mouseEnteredItem(index)"
             @mousemove="mouseEnteredItem(index)"
             v-bind:class="{'suggestion-item-hover': index == highlightIndex}"
             v-html="highlight(item)"></div>
      </div>
    </div>
  </div>
</template>

<script>
  export default {
    props:{
      value: String,
      getSuggestions: Function,
      delay: {
        type: Number,
        default: 500,
      },
      disabled: {
        type: Boolean,
        default: false,
      },
    },
    data () {
      return {
        items: [],
        isFocused: false,
        isMouseInside: false,
        internalValue: undefined,
        getSuggestionsTimer: undefined,
        highlightIndex: 0,
      }
    },
    created () {
      this.internalValue = this.value;
    },
    computed: {
      visibleItems () {
        return this.isFocused ? this.items : [];
      },
    },
    watch: {
      value (value) {
        this.internalValue = value;
      },
      internalValue (value) {
        this.highlightIndex = 0;
        if (!this.isFocused) {
          return;
        }
        if (!value || !value.length) {
          this.items = [];
          return;
        }
        if (this.getSuggestions) {
          if (this.getSuggestionsTimer) {
            clearTimeout(this.getSuggestionsTimer);
            this.getSuggestionsTimer = undefined;
          }
          this.items = [];
          this.getSuggestionsTimer = setTimeout(() => {
            this.getSuggestions(value, (items) => {
              this.items = items;
              this.getSuggestionsTimer = undefined;
            });
          }, this.delay);
        }
      },
    },
    methods: {
      select (value) {
        this.internalValue = value;
        this.items = this.items.filter(x => x.toLowerCase().startsWith(value.toLowerCase()));
        this.makeFocused(false);
        this.$emit('select', value);
        this.updateValue();
      },
      updateValue () {
        this.$emit('input', this.internalValue);
      },
      makeFocused (focused) {
        if (!this.isMouseInside) {
          this.isFocused = focused;
        }
        if (!focused) {
          this.isMouseInside = false;
          this.$emit('blur');
        } else {
          this.$emit('focus');
        }
        
      },
      mouseEnteredItem (index) {
        this.highlightIndex = index;
      },
      highlight (item) {
        const splitValues = this.internalValue.toLowerCase().split(' ').filter(Boolean);
        let highlighted = '';
        let lastIndex = 0;
        const lowerCaseItem = item.toLowerCase();
        for (let split of splitValues) {
          let foundIndex = lowerCaseItem.indexOf(split, lastIndex);
          if (foundIndex < 0) {
            continue;
          }
          highlighted += item.slice(lastIndex, foundIndex);
          lastIndex += foundIndex - lastIndex;
          let highlightedPiece = item.slice(foundIndex, foundIndex + split.length);
          highlighted += '<b style="background: #dadada">' + highlightedPiece + '</b>';
          lastIndex += split.length;
        }
        highlighted += item.slice(lastIndex);
        return highlighted;
      },
      arrowKey (direction) {
        const itemsLength = this.items.length;
        if (!itemsLength) {
          this.highlightIndex = 0;
          return;
        }
        this.highlightIndex = (itemsLength + this.highlightIndex + direction) % itemsLength;
      },
      enterKey (){
        if (!this.items.length) {
          return;
        }
        this.select(this.items[this.highlightIndex]);
      }
    }
  }
</script>

<style scoped>
.suggestion-list-wrapper {
  position: relative;
  z-index: 100;
}
.suggestion-list {
  margin: 2px;
  width: calc(100% - 4px);
  background: #fff;
  position: absolute;
  cursor: pointer;
}
.suggestion-item {
  padding: 4px;
  margin-top: 2px;
  margin-bottom: 2px;
}
.suggestion-item-hover {
  background: #eeeeee;
}
</style>
