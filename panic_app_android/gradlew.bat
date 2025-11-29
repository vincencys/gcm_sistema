@if "%DEBUG%" == "" @echo off
@rem ##########################################################################
@rem # Gradle startup script for Windows
@rem ##########################################################################

@rem Set default JVM options
set DEFAULT_JVM_OPTS=-Xmx64m -Xms64m

@rem --- Force JAVA_HOME to Android Studio embedded JBR if available (override broken global JAVA_HOME) ---
if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
	set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
)

set DIRNAME=%~dp0
if "%DIRNAME%" == "" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%

set CLASSPATH=%APP_HOME%\gradle\wrapper\gradle-wrapper.jar

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if "%ERRORLEVEL%" == "0" goto init

echo.
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.
goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME%
set JAVA_EXE=%JAVA_HOME%\bin\java.exe

if exist "%JAVA_EXE%" goto init

echo.
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.
goto fail

:init
@rem Collect all arguments for the java command
set CMD_LINE_ARGS=
set _SKIP=2

:winargs
if "%~1"=="" goto execute
set CMD_LINE_ARGS=%*

:execute
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %CMD_LINE_ARGS%
goto end

:fail
rem Set variable GRADLE_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
if  not "" == "%GRADLE_EXIT_CONSOLE%" exit 1
exit /b 1

:end
exit /b 0
