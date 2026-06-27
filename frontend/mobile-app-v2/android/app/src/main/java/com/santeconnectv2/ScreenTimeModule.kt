package com.santeconnectv2

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.provider.Settings
import com.facebook.react.bridge.*

class ScreenTimeModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName() = "ScreenTimeModule"

    /**
     * Retourne le temps d'écran total du jour en millisecondes.
     * Nécessite la permission PACKAGE_USAGE_STATS (accordée manuellement par l'user).
     */
    @ReactMethod
    fun getDailyScreenTime(promise: Promise) {
        try {
            val usm = reactApplicationContext
                .getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

            val now = System.currentTimeMillis()
            val startOfDay = now - (now % 86_400_000) // minuit UTC approx

            val stats = usm.queryUsageStats(
                UsageStatsManager.INTERVAL_DAILY,
                startOfDay,
                now,
            )

            if (stats.isNullOrEmpty()) {
                // Permission pas accordée ou aucune donnée
                promise.resolve(-1.0)
                return
            }

            val totalMs = stats.sumOf { it.totalTimeInForeground }
            val hours   = totalMs.toDouble() / 3_600_000.0
            promise.resolve(hours)
        } catch (e: Exception) {
            promise.reject("SCREEN_TIME_ERROR", e.message, e)
        }
    }

    /**
     * Vérifie si la permission PACKAGE_USAGE_STATS est accordée.
     */
    @ReactMethod
    fun hasPermission(promise: Promise) {
        try {
            val usm = reactApplicationContext
                .getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val now   = System.currentTimeMillis()
            val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - 1000, now)
            promise.resolve(!stats.isNullOrEmpty())
        } catch (e: Exception) {
            promise.resolve(false)
        }
    }

    /**
     * Ouvre les paramètres d'accès à l'utilisation des apps.
     */
    @ReactMethod
    fun openPermissionSettings(promise: Promise) {
        try {
            val intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            reactApplicationContext.startActivity(intent)
            promise.resolve(true)
        } catch (e: Exception) {
            promise.reject("OPEN_SETTINGS_ERROR", e.message, e)
        }
    }
}