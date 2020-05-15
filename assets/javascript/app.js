import { get, set } from 'js-cookie';

export { Exports } from './exports';

// pass-through for Cookies API
export const Cookies = {
  get: get,
  set: set,
};
