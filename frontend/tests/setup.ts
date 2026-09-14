import "@testing-library/jest-dom/vitest";

// Radix's Select (and other popup primitives) call these DOM APIs, which
// jsdom does not implement — without stubs, opening a Select in a test
// throws "not a function" before any assertion runs.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
