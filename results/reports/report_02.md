# Supply-chain exposure - `maven/io.zonky.test:embedded-database-spring-test@1.3.1`
_generated 2026-09-01_

**164 exposures** need action - 3 findings suppressed (with reason) - an `npm audit`-style tool would show all 167.

## Transitive exposures (each carries the path that proves it)

### CVE-2024-1597  -  CRITICAL (10.0)  -  depth 1
```
[CVE-2024-1597  cvss=10.0] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.postgresql:postgresql@42.2.2
```

### CVE-2016-1000027  -  CRITICAL (9.8)  -  depth 2
```
[CVE-2016-1000027  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.springframework:spring-web@5.1.5.RELEASE
```

### CVE-2023-26119  -  CRITICAL (9.8)  -  depth 2
```
[CVE-2023-26119  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> net.sourceforge.htmlunit:htmlunit@2.33
```

### CVE-2022-22965  -  CRITICAL (9.8)  -  depth 2
```
[CVE-2022-22965  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.springframework:spring-beans@5.2.1.RELEASE
```

### CVE-2022-46337  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-46337  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.flywaydb.flyway-test-extensions:flyway-spring-test@5.1.0 -> org.springframework:spring-jdbc@5.1.5.RELEASE -> org.apache.derby:derby@10.15.1.3
```

### CVE-2022-23221  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-23221  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.flywaydb.flyway-test-extensions:flyway-spring-test@5.1.0 -> org.springframework:spring-jdbc@5.1.5.RELEASE -> com.h2database:h2@1.4.197
```

### CVE-2021-42392  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2021-42392  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.flywaydb.flyway-test-extensions:flyway-spring-test@5.1.0 -> org.springframework:spring-jdbc@5.1.5.RELEASE -> com.h2database:h2@1.4.197
```

### CVE-2022-41853  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-41853  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.flywaydb.flyway-test-extensions:flyway-spring-test@5.1.0 -> org.springframework:spring-jdbc@5.1.5.RELEASE -> org.hsqldb:hsqldb@2.4.1
```

### CVE-2022-42889  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-42889  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> net.sourceforge.htmlunit:htmlunit@2.33 -> org.apache.commons:commons-text@1.6
```

### CVE-2019-17571  -  CRITICAL (9.8)  -  depth 5
```
[CVE-2019-17571  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.codehaus.gpars:gpars@1.2.1 -> org.jboss.netty:netty@3.2.10.Final -> log4j:log4j@1.2.17
```

### CVE-2022-23305  -  CRITICAL (9.8)  -  depth 5
```
[CVE-2022-23305  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.codehaus.gpars:gpars@1.2.1 -> org.jboss.netty:netty@3.2.10.Final -> log4j:log4j@1.2.17
```

### CVE-2022-23307  -  CRITICAL (9.8)  -  depth 5
```
[CVE-2022-23307  cvss=9.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.codehaus.gpars:gpars@1.2.1 -> org.jboss.netty:netty@3.2.10.Final -> log4j:log4j@1.2.17
```

### CVE-2022-37865  -  CRITICAL (9.1)  -  depth 3
```
[CVE-2022-37865  cvss=9.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.apache.ivy:ivy@2.4.0
```

### CVE-2019-20444  -  CRITICAL (9.1)  -  depth 4
```
[CVE-2019-20444  cvss=9.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.codehaus.gpars:gpars@1.2.1 -> org.jboss.netty:netty@3.2.10.Final
```

### CVE-2022-23302  -  HIGH (8.8)  -  depth 5
```
[CVE-2022-23302  cvss=8.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.codehaus.gpars:gpars@1.2.1 -> org.jboss.netty:netty@3.2.10.Final -> log4j:log4j@1.2.17
```

### CVE-2021-39153  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39153  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39149  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39149  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39139  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39139  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39154  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39154  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39145  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39145  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39150  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39150  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39141  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39141  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39147  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39147  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39151  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39151  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39144  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39144  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39146  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39146  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39148  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39148  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2021-39152  -  HIGH (8.5)  -  depth 3
```
[CVE-2021-39152  cvss=8.5] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2022-1471  -  HIGH (8.3)  -  depth 3
```
[CVE-2022-1471  cvss=8.3] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.testng:testng@7.0.0 -> org.yaml:snakeyaml@1.25
```

### CVE-2022-46751  -  HIGH (8.2)  -  depth 3
```
[CVE-2022-46751  cvss=8.2] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> org.apache.ivy:ivy@2.4.0
```

### CVE-2022-41966  -  HIGH (8.2)  -  depth 3
```
[CVE-2022-41966  cvss=8.2] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2024-22262  -  HIGH (8.1)  -  depth 2
```
[CVE-2024-22262  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.springframework:spring-web@5.1.5.RELEASE
```

### CVE-2024-22243  -  HIGH (8.1)  -  depth 2
```
[CVE-2024-22243  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.springframework:spring-web@5.1.5.RELEASE
```

### CVE-2024-22259  -  HIGH (8.1)  -  depth 2
```
[CVE-2024-22259  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.springframework:spring-web@5.1.5.RELEASE
```

### CVE-2020-5529  -  HIGH (8.1)  -  depth 2
```
[CVE-2020-5529  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> net.sourceforge.htmlunit:htmlunit@2.33
```

### CVE-2026-54512  -  HIGH (8.1)  -  depth 3
```
[CVE-2026-54512  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> com.jayway.jsonpath:json-path@2.4.0 -> com.fasterxml.jackson.core:jackson-databind@2.10.2
```

### CVE-2026-54513  -  HIGH (8.1)  -  depth 3
```
[CVE-2026-54513  cvss=8.1] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> com.jayway.jsonpath:json-path@2.4.0 -> com.fasterxml.jackson.core:jackson-databind@2.10.2
```

### CVE-2020-26217  -  HIGH (8.0)  -  depth 3
```
[CVE-2020-26217  cvss=8.0] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.codehaus.groovy:groovy@2.5.7 -> com.thoughtworks.xstream:xstream@1.4.11.1
```

### CVE-2022-4065  -  HIGH (7.8)  -  depth 2
```
[CVE-2022-4065  cvss=7.8] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.springframework:spring-test@5.1.5.RELEASE -> org.testng:testng@7.0.0
```

### CVE-2020-13692  -  HIGH (7.7)  -  depth 1
```
[CVE-2020-13692  cvss=7.7] io.zonky.test:embedded-database-spring-test@1.3.1 -> org.postgresql:postgresql@42.2.2
```

## Minimal remediation

- `maven/org.codehaus.groovy:groovy`  2.5.7 → **2.6.0-alpha-1**
- `maven/org.codehaus.groovy:groovy-all`  2.5.8 → **2.6.0-alpha-1**
- `maven/org.postgresql:postgresql`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework:spring-context`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.apache.commons:commons-compress`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.commons:commons-lang3`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.google.guava:guava`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework:spring-web`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/net.sourceforge.htmlunit:htmlunit`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework:spring-beans`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework:spring-webflux`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.testng:testng`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.jetbrains.kotlin:kotlin-stdlib`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.jayway.jsonpath:json-path`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/junit:junit`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.apache.derby:derby`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.h2database:h2`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.hsqldb:hsqldb`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.commons:commons-text`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.apache.ivy:ivy`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.thoughtworks.xstream:xstream`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.yaml:snakeyaml`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.fasterxml.jackson.core:jackson-databind`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.google.code.gson:gson`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.json:json`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.codehaus.jettison:jettison`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/net.minidev:json-smart`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.ant:ant`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.squareup.okhttp3:okhttp`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/xalan:xalan`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.squareup.okio:okio`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.jboss.netty:netty`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcprov-jdk14`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.fasterxml.jackson.core:jackson-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcpg-jdk14`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcpg-jdk15on`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/xerces:xercesImpl`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.bouncycastle:bcprov-jdk15on`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.httpcomponents:httpclient`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.eclipse.jetty:jetty-xml`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/commons-httpclient:commons-httpclient`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/log4j:log4j`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.google.protobuf:protobuf-java`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.eclipse.jetty:jetty-http`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.apache.commons:commons-vfs2`  ⚠️ **no safe fix**: only a major bump is clean

_2/164 exposures cleared by 2 bump(s)._

## Suppressed (present in the tree, not actioned)

| finding | why not an alert |
|---|---|
| GHSA-rm7j-f5g5-27vv (high) | `only_withdrawn_advisories` |
| GHSA-3mq5-fq9h-gj7j (none) | `only_withdrawn_advisories` |
| CVE-2021-22570 (high) | `only_withdrawn_advisories` |