# Spring Boot — what to look for

Spring Boot services are usually layered controller → service → repository, with
configuration and cross-cutting concerns wired through dependency injection. Read
in this order to reconstruct the architecture efficiently.

## High-signal files

| Concern | Where to look |
|---------|---------------|
| Entry point | Class annotated `@SpringBootApplication` (the detector finds it) |
| Build & deps | `pom.xml` or `build.gradle` — note the `spring-boot-starter-*` set |
| HTTP surface | `@RestController` / `@Controller` classes; their `@RequestMapping`/`@GetMapping` etc. |
| Business logic | `@Service` classes |
| Persistence | `@Repository`, Spring Data interfaces (`extends JpaRepository<…>`), `@Entity` classes |
| Data model | `@Entity` / `@Table` classes and their `@OneToMany`/`@ManyToOne` relations |
| Config | `application.yml` / `application.properties`, `@Configuration` classes, `@ConfigurationProperties` |
| Security | `SecurityConfig`, `WebSecurityConfigurerAdapter`/`SecurityFilterChain`, `@PreAuthorize` |
| Messaging | `@KafkaListener`, `@RabbitListener`, `@Scheduled`, `@Async` |
| External calls | `RestTemplate`/`WebClient`/`FeignClient` usages |

## Mapping to the architecture doc

- **System context:** the service itself, its callers (other services, gateway,
  frontend), and external systems it talks to (DB, message broker, third-party APIs
  found via Feign/WebClient).
- **Component view:** controllers → services → repositories, plus config/security as
  cross-cutting boxes.
- **Data model:** an `erDiagram` built from the `@Entity` classes and their JPA
  relationships. Column-level detail is optional; entities + relationships are the
  point.
- **Runtime flow:** pick one meaningful endpoint and trace controller → service →
  repository → DB and back as a `sequenceDiagram`.

## Things worth calling out as decisions/ADRs

- Sync vs. reactive (Spring MVC vs. WebFlux).
- Persistence choice (JPA/Hibernate vs. JDBC vs. MongoDB).
- How transactions are managed (`@Transactional` boundaries).
- Auth model (JWT, OAuth2 resource server, session).
- Profiles and externalised config.
