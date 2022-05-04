import axios from 'axios';

export const roleMixin = {

  created() {
    // this.fetchUserInfo();
  },
  methods: {
    fetchUserInfo() {
      const component = this;
      axios.get('restapi/users/get').then(response => {
        const user = response.data;
        console.log('User name: ' + user.user_name + ' (' + user.username + ') ' + user.role);
        component.$store.commit('setUserInfo', user);
      });
    },
    role(roleName) {
      const user = this.getUserInfo();
      if (!user) {
        return false;
      }
      const roles = ['anonymous',
        'user',
        'mc_contact',
        'generator_convener',
        'production_manager',
        'production_expert',
        'administrator',
      ];
      const role = user.role;
      const userRoleIndex = roles.indexOf(role);
      if (userRoleIndex === -1) {
        console.error('Unknown role: ' + role);
        return false;
      }
      const roleIndex = roles.indexOf(roleName);
      if (roleIndex === -1) {
        console.error('Unknown role: ' + roleName);
        return false;
      }
      return userRoleIndex >= roleIndex;
    },
    getUserInfo() {
      return this.$store.state.user;
    },
  },
};
