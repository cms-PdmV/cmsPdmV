<template>
  <div>
    <ul>
      <li v-for="(item, index) in value" :key="item">{{item}} <small v-if="!disabled" @click="deleteItem(index)" class="bold-hover remove-button">Remove</small></li>
      <li v-if="isEditing" class="input-field">
        <autocompleter v-model="newValue" :getSuggestions="getSuggestions" v-on:blur="endEdit" v-on:select="selectValue"></autocompleter>
      </li>
      <li v-if="!disabled && !isEditing">
        <small @click="startEdit()" class="bold-hover add-button">Add</small>
      </li>
    </ul>
  </div>
</template>

<script>

import Autocompleter from './Autocompleter';

export default {
  components: {
    Autocompleter,
  },
  props:{
    value: {
      type: Array,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    getSuggestions: {
      type: Function,
      default: function(value){
        console.warn('getSuggestions not implemented');
        return [];
      },
    },
  },
  data() {
    return {
      isEditing: false,
      newValue: '',
    };
  },
  methods: {
    deleteItem: function(index) {
      this.value.splice(index, 1);
    },
    startEdit: function() {
      this.newValue = '';
      this.isEditing = true;
    },
    stopEdit: function() {
      this.cancelEdit();
    },
    endEdit: function() {
      let value = this.newValue;
      value = value.trim();
      if (!value.length) {
        this.cancelEdit();
      }
    },
    selectValue: function(value) {
      if (!this.value.includes(value)) {
        this.value.push(value);
      }
      this.newValue = '';
      this.cancelEdit();
    },
    cancelEdit: function() {
      this.isEditing = false;
    },
  }
}
</script>

<style scoped>

.remove-button {
  color: red;
  cursor: pointer;
}

.add-button {
  color: green;
  cursor: pointer;
}

</style>