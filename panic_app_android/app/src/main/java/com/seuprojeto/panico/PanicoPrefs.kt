package com.seuprojeto.panico

import android.content.Context

object PanicoPrefs {
    private const val PREFS = "panic_prefs"

    fun saveStatus(ctx: Context, id: String?, status: String?, motivo: String?, action: String?) {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
        p.putString("last_status", status ?: "")
        p.putString("last_motivo", motivo ?: "")
        p.putString("last_action", action ?: "")
        p.putString("last_id", id ?: "")
        p.putLong("last_ts", System.currentTimeMillis())
        p.apply()
    }

    fun readStatus(ctx: Context): Map<String, Any?> {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return mapOf(
            "status" to p.getString("last_status", ""),
            "motivo" to p.getString("last_motivo", ""),
            "action" to p.getString("last_action", ""),
            "id" to p.getString("last_id", ""),
            "ts" to p.getLong("last_ts", 0L)
        )
    }
}
