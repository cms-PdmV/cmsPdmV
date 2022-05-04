<template>
  <div>
    <v-dialog v-model="visible" width="500">
      <v-card>
        <v-card-title>Delete?</v-card-title>
        <v-card-text>Are you sure you want to delete {{ itemsTitle }}?</v-card-text>
        <v-divider></v-divider>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="close()">No</v-btn>
          <v-btn color="error" @click="confirm()">Yes</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'delete-prompt',
  data() {
    return {
      visible: false,
      item: undefined,
      database: undefined,
      success: undefined,
      error: undefined,
    };
  },
  computed: {
    itemsTitle() {
      if (!this.item) {
        return '';
      }
      return this.item.prepid;
    },
  },
  created() {},
  methods: {
    open(database, item, onSuccess, onError) {
      this.visible = true;
      this.database = database;
      this.item = item;
      this.onSuccess = onSuccess;
      this.onError = onError;
    },
    close() {
      this.visible = false;
    },
    confirm() {
      this.close();
      console.log('Delete ' + this.item.prepid);
      axios
        .delete('restapi/' + this.database + '/delete/' + this.item.prepid)
        .then(
          (response) => {
            this.onSuccess(response.data);
          },
          (error) => {
            this.onError(error);
          },
        )
        .catch((error) => {
          this.onError(error);
        });
    },
  },
};
</script>
