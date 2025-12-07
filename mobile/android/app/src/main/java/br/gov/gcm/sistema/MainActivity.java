package br.gov.gcm.sistema;

import com.getcapacitor.BridgeActivity;
import br.gov.gcm.sistema.plugins.NativeSettingsPlugin;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import android.os.Bundle;
import android.content.pm.PackageManager;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebView;
import android.webkit.WebResourceResponse;
import android.webkit.WebViewClient;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.app.DownloadManager;
import android.os.Environment;
import android.widget.Toast;
import android.util.Log;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import android.content.Intent;
import android.net.Uri;
import android.provider.Settings;

public class MainActivity extends BridgeActivity {
	private static final int REQ_AUDIO = 9001;
	private static final int REQ_LOCATION = 9002;
	private static final int REQ_NOTIFICATIONS = 9003;

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		// Habilita debug do WebView (permitindo inspecionar via chrome://inspect)
		try { WebView.setWebContentsDebuggingEnabled(true); } catch (Exception ignored) {}
		
		// Interceptar links com PDF para abrir no navegador do sistema
		try {
			WebView webView = getBridge().getWebView();
			if (webView != null) {
				// Habilitar configurações para permitir fetch() e downloads
				webView.getSettings().setAllowFileAccess(true);
				webView.getSettings().setAllowContentAccess(true);
				webView.getSettings().setAllowFileAccessFromFileURLs(false); // Segurança
				webView.getSettings().setAllowUniversalAccessFromFileURLs(false); // Segurança
				webView.getSettings().setDomStorageEnabled(true);
				webView.getSettings().setDatabaseEnabled(true);
				webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(true);
				
				// Configurar listener para downloads
				webView.setDownloadListener(new DownloadListener() {
					@Override
					public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimetype, long contentLength) {
						try {
							DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
							request.setMimeType(mimetype);
							
							// Extrair nome do arquivo
							String filename = URLUtil.guessFileName(url, contentDisposition, mimetype);
							request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
							request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
							request.setTitle(filename);
							
							DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
							if (dm != null) {
								dm.enqueue(request);
								Toast.makeText(getApplicationContext(), "Baixando: " + filename, Toast.LENGTH_SHORT).show();
							}
						} catch (Exception e) {
							Log.e("MainActivity", "Erro no download: " + e.getMessage(), e);
							Toast.makeText(getApplicationContext(), "Erro ao baixar arquivo", Toast.LENGTH_SHORT).show();
						}
					}
				});
				
				webView.setWebViewClient(new WebViewClient() {
					@Override
					public boolean shouldOverrideUrlLoading(WebView view, String url) {
						String urlLower = url.toLowerCase();
						// Abrir arquivos PDF e views que servem PDF no navegador externo
						if (urlLower.endsWith(".pdf") || 
						    urlLower.contains("/servir_documento_assinado/") ||
						    urlLower.contains("/documento-assinado/")) {
							try {
								Intent intent = new Intent(Intent.ACTION_VIEW);
								intent.setData(Uri.parse(url));
								startActivity(intent);
								return true;
							} catch (Exception e) {
								Log.e("MainActivity", "Erro ao abrir URL: " + url, e);
							}
						}
						return false;
					}
					
					@Override
					public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
						// Permitir fetch() de recursos do mesmo domínio
						return super.shouldInterceptRequest(view, url);
					}
				});
			}
		} catch (Exception ignored) {}
		
			registerPlugin(NativeSettingsPlugin.class);
			createNotificationChannels();
		requestAudioPermissionIfNeeded();
		requestLocationPermissionIfNeeded();
		requestNotificationPermissionIfNeeded();
			// Dispara uma notificação de teste rápida para garantir que o app apareça
			// na lista de apps com notificação habilitável nas configurações do Android
			postWarmupNotification();
	}

		private void createNotificationChannels(){
			if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
				NotificationManager nm = getSystemService(NotificationManager.class);
				if (nm == null) return;
				NotificationChannel chDefault = new NotificationChannel(
					"default",
					"Notificações",
					NotificationManager.IMPORTANCE_HIGH
				);
				chDefault.setDescription("Alertas do Sistema GCM");
				chDefault.enableVibration(true);
				nm.createNotificationChannel(chDefault);

				NotificationChannel chFcm = new NotificationChannel(
					"fcm_fallback_notification_channel",
					"Mensagens",
					NotificationManager.IMPORTANCE_HIGH
				);
				chFcm.setDescription("Mensagens push (FCM)");
				chFcm.enableVibration(true);
				nm.createNotificationChannel(chFcm);
			}
		}

	private void requestAudioPermissionIfNeeded() {
		String perm = android.Manifest.permission.RECORD_AUDIO;
		if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
			ActivityCompat.requestPermissions(this, new String[]{perm}, REQ_AUDIO);
		}
	}

	private void requestLocationPermissionIfNeeded() {
		String fine = android.Manifest.permission.ACCESS_FINE_LOCATION;
		String coarse = android.Manifest.permission.ACCESS_COARSE_LOCATION;
		boolean fineGranted = ContextCompat.checkSelfPermission(this, fine) == PackageManager.PERMISSION_GRANTED;
		boolean coarseGranted = ContextCompat.checkSelfPermission(this, coarse) == PackageManager.PERMISSION_GRANTED;
		if (!fineGranted && !coarseGranted) {
			boolean shouldShowRationaleFine = ActivityCompat.shouldShowRequestPermissionRationale(this, fine);
			boolean shouldShowRationaleCoarse = ActivityCompat.shouldShowRequestPermissionRationale(this, coarse);
			if (shouldShowRationaleFine || shouldShowRationaleCoarse) {
				ActivityCompat.requestPermissions(this, new String[]{fine, coarse}, REQ_LOCATION);
			} else {
				ActivityCompat.requestPermissions(this, new String[]{fine, coarse}, REQ_LOCATION);
			}
		}
	}

	@Override
	public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
		super.onRequestPermissionsResult(requestCode, permissions, grantResults);
		if (requestCode == REQ_LOCATION) {
			boolean granted = false;
			for (int r : grantResults) { if (r == PackageManager.PERMISSION_GRANTED) { granted = true; break; } }
			if (!granted) {
				// Usuário negou. Se marcou "não perguntar novamente", ofereça abrir configurações.
				boolean fineDeniedForever = !ActivityCompat.shouldShowRequestPermissionRationale(this, android.Manifest.permission.ACCESS_FINE_LOCATION)
						&& ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED;
				boolean coarseDeniedForever = !ActivityCompat.shouldShowRequestPermissionRationale(this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
						&& ContextCompat.checkSelfPermission(this, android.Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED;
				if (fineDeniedForever || coarseDeniedForever) {
					try {
						Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
						intent.setData(Uri.fromParts("package", getPackageName(), null));
						intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
						startActivity(intent);
					} catch (Exception ignored) {}
				}
			}
		}
	}

	private void requestNotificationPermissionIfNeeded() {
		// A partir do Android 13 (API 33) é necessário pedir POST_NOTIFICATIONS em tempo de execução
		if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
			String perm = android.Manifest.permission.POST_NOTIFICATIONS;
			if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
				ActivityCompat.requestPermissions(this, new String[]{perm}, REQ_NOTIFICATIONS);
			}
		}
	}

	private void postWarmupNotification(){
		try{
			NotificationManagerCompat nmc = NotificationManagerCompat.from(this);
			NotificationCompat.Builder b = new NotificationCompat.Builder(this, "default")
				.setSmallIcon(R.mipmap.ic_launcher)
				.setContentTitle("Sistema GCM")
				.setContentText("Inicializando canal de notificação…")
				.setPriority(NotificationCompat.PRIORITY_HIGH)
				.setAutoCancel(true);
			int id = 1001;
			nmc.notify(id, b.build());
			new Handler(Looper.getMainLooper()).postDelayed(() -> {
				try { nmc.cancel(id); } catch(Exception ignored) {}
			}, 1200);
		}catch(Exception ignored){ }
	}
}
