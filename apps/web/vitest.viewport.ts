// jsdom has no layout engine. This lets tests choose which side of the xl breakpoint they are on.
let wide = true;

export const setWideScreen = (value: boolean) => {
  wide = value;
};

export function installViewportStubs() {
  window.matchMedia = ((query: string) => ({
    matches: wide,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;

  // Minimal <dialog> behaviour (jsdom lacks showModal/close).
  const proto = HTMLDialogElement.prototype;
  proto.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}
