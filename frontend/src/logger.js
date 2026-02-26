const baseLogger = (scope) => {
  const prefix = scope ? `[${scope}]` : "[app]";
  return {
    info: (...args) => console.info(prefix, ...args),
    warn: (...args) => console.warn(prefix, ...args),
    error: (...args) => console.error(prefix, ...args),
    debug: (...args) => console.debug(prefix, ...args),
    child: (childScope) => baseLogger(`${scope}:${childScope}`)
  };
};

export const logger = baseLogger("frontend");
