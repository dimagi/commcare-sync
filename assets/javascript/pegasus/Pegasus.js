import { get, set } from 'js-cookie';
export { Api } from './Api';

// pass-through for Cookies API
export const Cookies = {
  get: get,
  set: set,
};
