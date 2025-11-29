package br.gov.gcm.sistema;

import android.app.Application;
import com.google.firebase.FirebaseApp;

public class MyApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        // Garantir inicialização do Firebase antes de qualquer uso (ex.: PushNotifications)
        try {
            FirebaseApp.initializeApp(this);
        } catch (Exception ignored) {
            // Evita crash em cenários sem google-services, mas registra via provider quando disponível
        }
    }
}
