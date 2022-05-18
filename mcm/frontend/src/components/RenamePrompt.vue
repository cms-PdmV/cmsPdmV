<template>
  <div>
    <v-dialog v-model="visible" persistent width="500">
      <v-card>
        <v-card-title>Rename</v-card-title>
        <v-card-text class="edit-table">
          New name: <input type="text" v-model="value"/>
        </v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="error" @click="close()">Cancel</v-btn>
          <v-btn color="success" @click="confirm()">Rename</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>

export default {
  name: 'sequence-edit',
  data() {
    return {
      visible: false,
      value: undefined,
      onSave: undefined,
    };
  },
  methods: {
    open(value, onSave) {
      this.visible = true;
      this.value = value;
      this.onSave = onSave;
    },
    close() {
      this.visible = false;
    },
    confirm() {
      this.close();
      this.onSave(this.value);
    },
  },
};
</script>
