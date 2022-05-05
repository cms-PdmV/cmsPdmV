<template>
  <div>
    <v-dialog v-model="visible" width="500">
      <v-card>
        <v-card-title>Oopsie woopsie :(</v-card-title>
        <v-card-text>{{ errorMessage }}</v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="close()">Ok</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
export default {
  name: 'error-dialog',
  data() {
    return {
      visible: false,
      errorMessage: undefined,
    };
  },
  created() {},
  methods: {
    open(errorMessage) {
      this.visible = true;
      this.errorMessage = errorMessage;
    },
    close() {
      this.visible = false;
    },
  },
};
</script>
