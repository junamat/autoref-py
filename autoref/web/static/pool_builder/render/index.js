import { renderTree } from './tree.js';
import { renderDetail } from './detail.js';

export function rerender() {
  renderTree();
  renderDetail();
}
