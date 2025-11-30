# Flavors e Branding por Cidade

Com a remoção da seleção de cidade na interface, cada cidade agora terá seu próprio APK com:

## Estrutura de Flavors

Cada flavor define:
- **applicationIdSuffix**: sufixo único para o package name
- **app_name** (via resValue): nome exibido no launcher
- **API_BASE_URL** (via buildConfigField): URL do backend da cidade
- **CITY_NAME** (via buildConfigField): nome da cidade (disponível como `BuildConfig.CITY_NAME`)

### Exemplo de flavor no `app/build.gradle`:

```gradle
flavorDimensions "city"
productFlavors {
    gcmsysint {
        dimension "city"
        applicationIdSuffix ".gcmsysint"
        resValue "string", "app_name", "SafeBP GCM Sistema"
        buildConfigField "String", "API_BASE_URL", '"https://gcmsysint.online"'
        buildConfigField "String", "CITY_NAME", '"GCM Sistema"'
    }
    devusb {
        dimension "city"
        applicationIdSuffix ".devusb"
        resValue "string", "app_name", "SafeBP DEV USB"
        buildConfigField "String", "API_BASE_URL", '"http://127.0.0.1:8000"'
        buildConfigField "String", "CITY_NAME", '"DEV USB"'
    }
}
```

## Adicionando uma Nova Cidade

1. **Definir o flavor no `app/build.gradle`**:
   ```gradle
   campinas {
       dimension "city"
       applicationIdSuffix ".campinas"
       resValue "string", "app_name", "SafeBP Campinas"
       buildConfigField "String", "API_BASE_URL", '"https://api.campinas.sp.gov.br"'
       buildConfigField "String", "CITY_NAME", '"Campinas"'
   }
   ```

2. **Criar configuração do Firebase (opcional)**:
   - Baixe o `google-services.json` do projeto Firebase da cidade
   - Coloque em `app/src/campinas/google-services.json`

3. **Branding personalizado (opcional)**:
   - Ícones: `app/src/campinas/res/mipmap-*/ic_launcher.png`
   - Cores/strings: `app/src/campinas/res/values/colors.xml`, `strings.xml`

4. **Build do APK para a cidade**:
   ```powershell
   cd panic_app_android
   .\gradlew assembleCampinasRelease
   ```

## Estrutura de Arquivos para Branding

```
app/
├── build.gradle (flavors definidos aqui)
├── src/
│   ├── main/ (código comum)
│   ├── gcmsysint/
│   │   ├── google-services.json
│   │   └── res/
│   │       ├── mipmap-*/
│   │       └── values/
│   ├── campinas/
│   │   ├── google-services.json
│   │   └── res/
│   │       ├── mipmap-*/
│   │       └── values/
│   └── ...
```

## Comandos Úteis

- Listar todas as variantes:
  ```powershell
  .\gradlew tasks --all | Select-String "assemble"
  ```

- Build de todos os APKs:
  ```powershell
  .\gradlew assembleRelease
  ```

- Build de um flavor específico:
  ```powershell
  .\gradlew assembleGcmsysintRelease
  .\gradlew assembleDevusbDebug
  ```

## Observações

- O manifesto usa `@string/app_name` do flavor para o nome exibido no launcher.
- `BuildConfig.API_BASE_URL` é acessível em toda a base de código (MainActivity, RegisterActivity, Services).
- Cada flavor gera um APK com package name diferente, permitindo instalar múltiplos APKs (um por cidade) no mesmo dispositivo para testes.
