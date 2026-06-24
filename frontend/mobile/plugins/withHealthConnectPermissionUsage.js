const { withAndroidManifest } = require("@expo/config-plugins");

/**
 * Config plugin Expo — déclaration Android 14+ requise par Health Connect.
 *
 * Sur Android 14+ (dont Android 16), Health Connect exige que l'app déclare une
 * `activity-alias` gérant l'intent `VIEW_PERMISSION_USAGE` avec la catégorie
 * `HEALTH_PERMISSIONS` (lien vers la politique de confidentialité des données
 * de santé). Le plugin de `react-native-health-connect@3.5.3` n'ajoute que
 * l'ancienne déclaration (`ACTION_SHOW_PERMISSIONS_RATIONALE`), ce qui provoque
 * un CRASH NATIF lors de `requestPermission()` sur Android 14+.
 *
 * Ce plugin ajoute l'activity-alias manquante au manifest généré.
 */
module.exports = function withHealthConnectPermissionUsage(config) {
  return withAndroidManifest(config, (cfg) => {
    const app = cfg.modResults.manifest.application[0];
    app["activity-alias"] = app["activity-alias"] || [];

    const already = app["activity-alias"].some(
      (a) => a.$ && a.$["android:name"] === "ViewPermissionUsageActivity",
    );
    if (!already) {
      app["activity-alias"].push({
        $: {
          "android:name": "ViewPermissionUsageActivity",
          "android:exported": "true",
          "android:targetActivity": ".MainActivity",
          "android:permission": "android.permission.START_VIEW_PERMISSION_USAGE",
        },
        "intent-filter": [
          {
            action: [
              {
                $: {
                  "android:name": "android.intent.action.VIEW_PERMISSION_USAGE",
                },
              },
            ],
            category: [
              {
                $: {
                  "android:name": "android.intent.category.HEALTH_PERMISSIONS",
                },
              },
            ],
          },
        ],
      });
    }
    return cfg;
  });
};
