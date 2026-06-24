/**
 * Config plugin Expo — injecte le "permission delegate" de Health Connect dans
 * MainActivity.onCreate (Kotlin).
 *
 * react-native-health-connect@3.5.3 définit `setPermissionDelegate()` mais ne
 * l'appelle JAMAIS automatiquement. Or `requestPermission` est un `lateinit`
 * initialisé uniquement par cet appel. Sans lui, `requestPermission()` plante
 * avec « lateinit property requestPermission has not been initialized » sur
 * Android 14+ (crash natif observé sur Android 16, Samsung).
 *
 * En React Native "bare" on l'ajoute à la main dans MainActivity ; en Expo
 * géré (pas de MainActivity dans le repo), ce plugin l'injecte au build.
 */
const { withMainActivity } = require("@expo/config-plugins");

const IMPORT =
  "import dev.matinzd.healthconnect.permissions.HealthConnectPermissionDelegate";
const CALL = "    HealthConnectPermissionDelegate.setPermissionDelegate(this)";

module.exports = function withHealthConnectDelegate(config) {
  return withMainActivity(config, (cfg) => {
    let src = cfg.modResults.contents;

    if (src.includes("HealthConnectPermissionDelegate")) {
      return cfg; // déjà injecté
    }

    // 1) Import après la ligne `package ...`
    src = src.replace(/^(package .*)$/m, `$1\n\n${IMPORT}`);

    // 2) Appel juste après super.onCreate(...) dans onCreate
    src = src.replace(/(super\.onCreate\([^)]*\))/, `$1\n${CALL}`);

    cfg.modResults.contents = src;
    return cfg;
  });
};
