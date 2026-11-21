Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — civilizaciones autónomas con IA

**Modelos de lenguaje locales. Países independientes. Una historia formada por decisiones reales.**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet es un simulador de gran estrategia en el que entre 2 y 6 países toman decisiones mediante modelos de lenguaje ejecutados localmente. Cada país tiene recursos, territorio, planes, relaciones diplomáticas y memoria propios. Crea un mundo y observa cómo construyen, negocian, comercian, luchan y afrontan las consecuencias.

## Cómo funciona la simulación

El motor de Python comprueba las órdenes estructuradas de la IA según el territorio, los recursos, las tecnologías, las rutas y los tratados. Decir «construyo una fábrica» no crea una fábrica si no puede construirse y pagarse.

55 tipos de acciones · 31 recursos · 2 eras · 25 + 33 tecnologías · 45 edificios de la era industrial · 8 tipos de tropas modernas. La economía incluye trabajadores, cadenas de producción, energía, mantenimiento, suministros y crisis. Los mapas se generan mediante una semilla reproducible y existe un modo archipiélago.

## Inicio rápido

1. Instala Python 3.12 y LM Studio. Descarga un modelo instruct/chat capaz de generar JSON estructurado y activa el servidor desde **Developer**.
2. Descarga el repositorio en ZIP, descomprímelo en una carpeta con permiso de escritura y ejecuta `install.bat` en Windows.
3. Abre `run.bat`; entra en **LM Studio** (o `F2`), indica `http://localhost:1234/v1`, actualiza la lista y elige un modelo.
4. Crea un mundo con 2–6 países y selecciona **Un día** o **Observar** (las etiquetas actuales de la interfaz están en ruso).

```bash
python -m pip install -r requirements.txt
python main.py
```

**La descarga **no incluye** modelos de IA, pesos, partidas guardadas ni claves API. La versión publicada v8.0.0 requiere un servidor compatible; no inicia modelos directamente desde la carpeta `models`. La memoria y las recompensas proporcionan información de retorno, **pero no ajustan los pesos del modelo**.**

![Archipelago mode](../../assets/archipelago.png)

## Documentación y licencia

- [Guía de instalación](SETUP.md)
- [Manual completo (en ruso)](../../GAME_GUIDE.md)
- [Galería de capturas](../../SCREENSHOTS.md)
- [Licencia: distribución gratuita y atribución obligatoria](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

El manual completo y la documentación técnica original están en ruso. Esta página y la guía de instalación localizada son traducciones introductorias, **no** una traducción de la interfaz del juego.

Al distribuir o modificar este proyecto, conserva el nombre del creador original y el enlace al repositorio.
