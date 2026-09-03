# Supply-chain exposure - `maven/cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27`
_generated 2026-09-02_

**286 exposures** need action - 9 findings suppressed (with reason) - an `npm audit`-style tool would show all 295.

## Transitive exposures (each carries the path that proves it)

### CVE-2021-44228  -  CRITICAL (10.0)  -  depth 3
```
[CVE-2021-44228  cvss=10.0] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.logging.log4j:log4j-core@2.12.1
```

### CVE-2024-56337  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2024-56337  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2024-50379  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2024-50379  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2025-24813  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2025-24813  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2020-1938  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2020-1938  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2026-43512  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2026-43512  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2026-41293  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2026-41293  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.apache.tomcat.embed:tomcat-embed-core@9.0.24
```

### CVE-2022-0839  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-0839  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.liquibase:liquibase-core@3.8.5
```

### CVE-2022-22965  -  CRITICAL (9.8)  -  depth 3
```
[CVE-2022-22965  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot@2.1.7.RELEASE -> org.springframework:spring-webflux@5.2.1.RELEASE
```

### CVE-2020-13957  -  CRITICAL (9.8)  -  depth 4
```
[CVE-2020-13957  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot-autoconfigure@2.1.7.RELEASE -> org.springframework.data:spring-data-solr@4.1.0.RELEASE -> org.apache.solr:solr-core@8.4.0
```

### CVE-2025-24814  -  CRITICAL (9.8)  -  depth 4
```
[CVE-2025-24814  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot-autoconfigure@2.1.7.RELEASE -> org.springframework.data:spring-data-solr@4.1.0.RELEASE -> org.apache.solr:solr-core@8.4.0
```

### CVE-2019-17571  -  CRITICAL (9.8)  -  depth 4
```
[CVE-2019-17571  cvss=9.8] cc.catalysts.boot:cat-boot-thymeleaf3@0.2.27 -> org.springframework.boot:spring-boot-starter@2.1.7.RELEASE -> org.springframework.boot:spring-boot-autoconfigure@2.1.7.RELEASE -> com.hazelcast:hazelcast@3.12-BETA-1 -> log4j:log4j@1.2.17
```

## Minimal remediation

- `maven/org.thymeleaf:thymeleaf`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.yaml:snakeyaml`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.fasterxml.jackson.core:jackson-databind`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.boot:spring-boot`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.boot:spring-boot-autoconfigure`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.logging.log4j:log4j-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.tomcat.embed:tomcat-embed-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.liquibase:liquibase-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework:spring-webflux`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework:spring-beans`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.hazelcast:hazelcast`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework.data:spring-data-mongodb`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.kafka:spring-kafka`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.google.code.gson:gson`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.eclipse.jetty.http2:http2-server`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.tomcat.embed:tomcat-embed-websocket`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.fasterxml.jackson.core:jackson-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.hibernate.validator:hibernate-validator`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.hibernate:hibernate-validator`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/ch.qos.logback:logback-classic`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.eclipse.jetty:jetty-webapp`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.assertj:assertj-core`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.codehaus.groovy:groovy`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.codehaus.groovy:groovy-all`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.jetbrains.kotlin:kotlin-stdlib`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.eclipse.jetty.http2:http2-common`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.eclipse.jetty:jetty-servlets`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/junit:junit`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.apache.solr:solr-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/log4j:log4j`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework:spring-web`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.security:spring-security-web`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.ivy:ivy`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.elasticsearch:elasticsearch`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.thoughtworks.xstream:xstream`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.querydsl:querydsl-jpa`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.querydsl:querydsl-apt`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.data:spring-data-rest-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/io.micrometer:micrometer-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.ant:ant`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.eclipse.jetty:jetty-server`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.springframework.data:spring-data-commons`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework:spring-context`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework:spring-core`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.fasterxml.woodstox:woodstox-core`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.commons:commons-lang3`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.springframework.data:spring-data-keyvalue`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/com.google.guava:guava`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.eclipse.jetty:jetty-http`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.jayway.jsonpath:json-path`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.eclipse.jetty:jetty-xml`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.jboss.netty:netty`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.testng:testng`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.bouncycastle:bcprov-jdk14`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcpg-jdk14`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcpg-jdk15on`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.xerial.snappy:snappy-java`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.json:json`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.codehaus.jettison:jettison`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/net.minidev:json-smart`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.bouncycastle:bcprov-jdk15on`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.httpcomponents:httpclient`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/commons-httpclient:commons-httpclient`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/xalan:xalan`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/com.google.protobuf:protobuf-java`  ⚠️ **no safe fix**: no published version is free of advisories
- `maven/org.apache.commons:commons-vfs2`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/xerces:xercesImpl`  ⚠️ **no safe fix**: only a major bump is clean
- `maven/org.eclipse.jetty:jetty-security`  ⚠️ **no safe fix**: only a major bump is clean

_0/286 exposures cleared by 0 bump(s)._

## Suppressed (present in the tree, not actioned)

| finding | why not an alert |
|---|---|
| GHSA-q4h9-7rxj-7gx2 (medium) | `only_withdrawn_advisories` |
| GHSA-wpvf-5mc3-hv6m (critical) | `only_withdrawn_advisories` |
| GHSA-fv22-xp26-mm9w (high) | `only_withdrawn_advisories` |
| GHSA-3mq5-fq9h-gj7j (none) | `only_withdrawn_advisories` |
| GHSA-4rv7-wj6m-6c6r (none) | `only_withdrawn_advisories` |
| GHSA-5hc5-c3m9-8vcj (none) | `only_withdrawn_advisories` |
| GHSA-9fwf-46g9-45rx (none) | `only_withdrawn_advisories` |
| GHSA-rm7j-f5g5-27vv (high) | `only_withdrawn_advisories` |
| CVE-2021-22570 (high) | `only_withdrawn_advisories` |