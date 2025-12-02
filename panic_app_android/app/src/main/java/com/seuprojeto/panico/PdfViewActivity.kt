package com.seuprojeto.panico

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

class PdfViewActivity : AppCompatActivity() {
    companion object {
        const val EXTRA_URL = "pdf_url"
        const val EXTRA_TITLE = "pdf_title"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val webView = WebView(this)
        setContentView(webView)

        // Suporta tanto extra explícito quanto Intent.ACTION_VIEW (data uri)
        var url = intent.getStringExtra(EXTRA_URL)
        val data = intent.data
        if (url.isNullOrBlank() && data != null) {
            url = data.toString()
        }
        val title = intent.getStringExtra(EXTRA_TITLE) ?: "Documento"
        supportActionBar?.title = title

        val settings: WebSettings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.loadWithOverviewMode = true
        settings.useWideViewPort = true
        settings.builtInZoomControls = true
        settings.displayZoomControls = false

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                return false
            }
        }

        // Usa Google Docs Viewer para PDFs remotos (compatível com maioria dos devices)
        val viewerUrl = if (!url.isNullOrBlank()) {
            "https://docs.google.com/gview?embedded=1&url=" + url
        } else {
            "about:blank"
        }
        webView.loadUrl(viewerUrl)
    }
}
