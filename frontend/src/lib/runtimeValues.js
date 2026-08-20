export const currentTimeMs = () => Date.now();

export const randomDelay = (minimumMs, rangeMs) => (
  Math.floor(Math.random() * rangeMs) + minimumMs
);

export const createClientMessageId = (offset = 0) => currentTimeMs() + offset;
