# BouncyCastle Java Library

The BouncyCastle library is required **only** if you intend to export certificates in `.bks` (Bouncy Castle KeyStore) format.

## Why Use `.bks`?
- `.bks` is often used for **Android apps**, **Java-based IoT clients**, or secure devices that rely on Java KeyStores.

## Installation Instructions

```bash
wget https://www.bouncycastle.org/download/bcprov-jdk15on-146.jar
sudo mv bcprov-jdk15on-146.jar /opt/
```

Then ensure your `.env` or environment variables include:

```bash
BOUNCYCASTLE_JAR_PATH=/opt/bcprov-jdk15on-146.jar
```

## Disabling BKS

If you're not using Java-based clients, you can safely ignore this setup and use `.p12` or `.tgz` cert exports instead.
