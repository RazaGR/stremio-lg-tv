/**
 * Configuration.
 *
 * Plain ES5 with no module system: this runs on TV browser engines as old as
 * Chromium 38, so no let/const, arrow functions, template literals or fetch().
 */
window.STREMIO_CONFIG = {

  /** The Stremio build to open. */
  url: 'https://tv.strem.io/',

  /**
   * Connection check, so a network problem reports itself instead of leaving a
   * black screen. Resolved RELATIVE TO `url`, so it always hits the origin we
   * actually open. Must be an image: image loads ignore CORS and work on
   * firmware too old for fetch().
   *
   * A URL that 404s serves an HTML error page, which cannot decode as an image
   * and looks exactly like the TV being offline. `make check-probe` guards this.
   * The path carries a build hash because that origin serves no unhashed image.
   */
  probeImage: '34e211e714f7f5dddc76aae346a949d305ce51cf/favicons/icon-96.png',

  /** Minimum time the boot screen stays up, so it does not just flash (ms). */
  minBootMs: 900,

  /** Give up on the connection check after this long (ms). */
  probeTimeoutMs: 8000,

  /**
   * How long the "trouble connecting" notice stays up before opening Stremio
   * anyway (ms). The check is a diagnostic, never a gate.
   */
  failOpenMs: 2500
};
