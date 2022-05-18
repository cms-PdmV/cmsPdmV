<template>
  <div>
    <v-dialog v-model="visible" persistent>
      <v-card>
        <v-card-title>Edit sequence {{sequenceName(item)}}</v-card-title>
        <v-card-text>
          <table class="edit-table">
            <tr v-for="key in sequenceKeys" :key="key">
              <td style="font-family: monospace; text-align: right;">--{{key}}</td>
              <td><input type="text" v-model="item[key]"/></td>
            </tr>
          </table>
        </v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" @click="close()">Cancel</v-btn>
          <v-btn color="success" @click="confirm()">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>

import { utilsMixin } from '../mixins/UtilsMixin.js';

export default {
  name: 'sequence-edit',
  mixins: [utilsMixin],
  data() {
    return {
      visible: false,
      item: undefined,
      onSave: undefined,
    };
  },
  computed: {
    sequenceKeys() {
      if (!this.item) {
        return [];
      }
      return Object.keys(this.item).sort();
    },
  },
  created() {},
  methods: {
    open(item, onSave) {
      this.visible = true;
      this.item = item;
      this.onSave = onSave;
    },
    close() {
      this.visible = false;
    },
    confirm() {
      this.close();
      this.onSave(this.item);
    },
  },
};
</script>

<style scoped>
td {
  padding: 2px;
}
</style>
