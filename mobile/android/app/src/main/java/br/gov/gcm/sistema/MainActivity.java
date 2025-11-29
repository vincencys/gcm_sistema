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
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

public class MainActivity extends BridgeActivity {
	private static final int REQ_AUDIO = 9001;
	private static final int REQ_LOCATION = 9002;
	private static final int REQ_NOTIFICATIONS = 9003;

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		// Habilita debug do WebView (permitindo inspecionar via chrome://inspect)
		try { WebView.setWebContentsDebuggingEnabled(true); } catch (Exception ignored) {}
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
			ActivityCompat.requestPermissions(this, new String[]{fine, coarse}, REQ_LOCATION);
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
