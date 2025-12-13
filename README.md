# PhD Tracker - Thesis-Quality Spring Boot Application

A production-grade PhD supervision and progress tracking system built with **Spring Boot 3.5.x** and **Java 21**, featuring milestone tracking, meeting scheduling, WhatsApp reminders, and Google Calendar integration.

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Security Model](#security-model)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Setup Instructions](#setup-instructions)
- [Sample Credentials](#sample-credentials)
- [Testing](#testing)
- [Production Deployment](#production-deployment)

---

## 🏗️ Architecture

### Layered Architecture

```
┌─────────────────────────────────────────┐
│          Controller Layer               │  ← REST API endpoints
│   (AuthController, SupervisorController) │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Service Layer                 │  ← Business logic
│  (AuthService, SupervisorService, etc.) │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Repository Layer                │  ← Data access
│   (UserRepository, StudentRepository)   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           MySQL Database                │
└─────────────────────────────────────────┘
```

### Package Structure

```
edu.university.phdtracker
├── config/                 # Configuration classes
├── controller/             # REST API controllers
├── dto/                    # Request/Response DTOs
├── entity/                 # JPA entities
├── repository/             # Spring Data JPA repositories
├── service/                # Service interfaces
│   └── impl/              # Service implementations
├── security/               # JWT & authentication
├── integration/            # External integrations (WhatsApp, Google Calendar)
└── exception/              # Global exception handling
```

---

## 💻 Technology Stack

| Layer                | Technology                          |
|----------------------|-------------------------------------|
| **Backend**          | Spring Boot 3.5.8, Java 21          |
| **Build Tool**       | Maven                               |
| **Security**         | Spring Security + JWT (JJWT 0.11.5) |
| **Database**         | MySQL 8.0+                          |
| **ORM**              | Spring Data JPA (Hibernate)         |
| **Validation**       | Jakarta Validation                  |
| **Utilities**        | Lombok, MapStruct (optional)        |

---

## 🔐 Security Model

### Authentication Flow

1. User submits credentials via `POST /api/auth/login`
2. System validates credentials using BCrypt password encoder
3. JWT token generated with user ID, email, and role
4. Client includes token in `Authorization: Bearer <token>` header for subsequent requests
5. JWT filter validates token and populates `SecurityContext` with `UserPrincipal`

### Authorization (RBAC)

| Role         | Access                                                     |
|--------------|------------------------------------------------------------|
| **ADMIN**    | User registration, system administration                   |
| **SUPERVISOR** | Student management, meeting scheduling, report generation |
| **STUDENT**  | Milestone updates, document uploads, notification access   |

### Security Configuration

- **Public Endpoints**: `/api/auth/**` (login, register)
- **Protected Endpoints**: All other APIs require valid JWT
- **Password Encryption**: BCrypt with strength 10
- **Token Expiration**: 24 hours (configurable via `jwt.expiration-ms`)

### JWT Token Structure

```json
{
  "sub": "user@phd.edu",
  "role": "SUPERVISOR",
  "userId": 2,
  "iat": 1702540800,
  "exp": 1702627200
}
```

---

## 🗄️ Database Schema

### Core Entities

1. **User** - Base user accounts (ADMIN, SUPERVISOR, STUDENT)
2. **Supervisor** - Extends User with department info
3. **Student** - Extends User with research details, linked to Supervisor
4. **Milestone** - Progress tracking milestones (PENDING, COMPLETED, APPROVED, DELAYED)
5. **Document** - Student document uploads with versioning
6. **Meeting** - Scheduled meetings between supervisors and students
7. **Notification** - System notifications (EMAIL, WHATSAPP)

### Entity Relationships

```
User (1) ──────> (1) Supervisor
                      │
                      │ (1:N)
                      ↓
                  Student ──> Milestone (1:N)
                      │
                      ├──> Document (1:N)
                      └──> Meeting (N:N via Supervisor)
                      
User (1) ──────> (N) Notification
```

---

## 📡 API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint           | Description            | Access  |
|--------|-------------------|------------------------|---------|
| POST   | `/auth/login`     | User login             | Public  |
| POST   | `/auth/register`  | Register new user      | ADMIN   |

**Login Request:**
```json
{
  "email": "prof1@phd.edu",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "role": "SUPERVISOR",
  "userId": 2
}
```

---

### Supervisor Endpoints (`/api/supervisor`)

| Method | Endpoint                    | Description                  | Role       |
|--------|-----------------------------|------------------------------|------------|
| POST   | `/students`                 | Add student to supervision   | SUPERVISOR |
| GET    | `/students`                 | List supervised students     | SUPERVISOR |
| POST   | `/meetings`                 | Schedule meeting             | SUPERVISOR |
| GET    | `/reports/{studentId}`      | Generate student report      | SUPERVISOR |

**Add Student Request:**
```json
{
  "userId": 4,
  "researchTitle": "AI in Healthcare",
  "status": "ACTIVE",
  "enrollmentDate": "2024-01-15T00:00:00Z"
}
```

---

### Student Endpoints (`/api/student`)

| Method | Endpoint              | Description              | Role    |
|--------|-----------------------|--------------------------|---------|
| PUT    | `/milestones/{id}`   | Update milestone status  | STUDENT |
| POST   | `/documents`          | Upload document          | STUDENT |
| GET    | `/notifications`      | Get notifications        | STUDENT |

**Update Milestone Request:**
```json
{
  "title": "Literature Review",
  "description": "Completed comprehensive survey",
  "status": "COMPLETED"
}
```

---

## 🚀 Setup Instructions

### Prerequisites

- **Java 21** (Oracle JDK or OpenJDK)
- **Maven 3.9+**
- **MySQL 8.0+** running on `localhost:3306`
- **Git** (for cloning)

### Step 1: Clone Repository

```bash
git clone https://github.com/vivekjindal24/phd-tracker.git
cd phd-tracker
```

### Step 2: Configure Database

Create MySQL database:

```sql
CREATE DATABASE phd_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or let the application auto-create it (enabled in `application.yml`).

### Step 3: Set Environment Variables (Optional)

```bash
export PHD_TRACKER_DB_USERNAME=root
export PHD_TRACKER_DB_PASSWORD=your_password
export PHD_TRACKER_JWT_SECRET=$(echo -n "your-secret-key-min-32-chars" | base64)
```

Or modify `src/main/resources/application.yml` directly.

### Step 4: Build Application

```bash
mvn clean package -DskipTests
```

### Step 5: Run Application

```bash
mvn spring-boot:run
```

Or run the JAR:

```bash
java -jar target/phd-tracker-0.0.1-SNAPSHOT.jar
```

Application starts on: **http://localhost:8080**

### Step 6: Verify Setup

Check health endpoint:

```bash
curl http://localhost:8080/actuator/health
```

Expected response:
```json
{"status":"UP"}
```

---

## 🔑 Sample Credentials

The application seeds sample users via `data.sql` on startup:

| Email               | Password      | Role       |
|---------------------|---------------|------------|
| admin@phd.edu       | password123   | ADMIN      |
| prof1@phd.edu       | password123   | SUPERVISOR |
| prof2@phd.edu       | password123   | SUPERVISOR |
| student1@phd.edu    | password123   | STUDENT    |
| student2@phd.edu    | password123   | STUDENT    |
| student3@phd.edu    | password123   | STUDENT    |

**BCrypt Hash Used**: `$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy`

---

## 🧪 Testing

### Login as Supervisor

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "prof1@phd.edu",
    "password": "password123"
  }'
```

**Save the token** from response.

### Get Supervised Students

```bash
curl http://localhost:8080/api/supervisor/students \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Login as Student

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student1@phd.edu",
    "password": "password123"
  }'
```

### Get Notifications

```bash
curl http://localhost:8080/api/student/notifications \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Run Unit Tests

```bash
mvn test
```

---

## 🌐 Production Deployment

### Security Checklist

- [ ] Change default JWT secret (`PHD_TRACKER_JWT_SECRET`)
- [ ] Use strong MySQL passwords
- [ ] Disable `spring.jpa.show-sql` in production
- [ ] Set `spring.sql.init.mode=never` after initial seed
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS for frontend domains
- [ ] Use connection pooling (HikariCP is default)
- [ ] Enable actuator security
- [ ] Set up logging (ELK, Splunk, etc.)

### Environment Variables

```bash
# Database
export PHD_TRACKER_DB_USERNAME=prod_user
export PHD_TRACKER_DB_PASSWORD=<strong-password>

# JWT (min 256-bit base64 secret)
export PHD_TRACKER_JWT_SECRET=<base64-encoded-secret>

# Spring Profile
export SPRING_PROFILES_ACTIVE=production
```

### Docker Deployment (Optional)

```dockerfile
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY target/phd-tracker-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

Build and run:

```bash
docker build -t phd-tracker .
docker run -p 8080:8080 \
  -e PHD_TRACKER_DB_USERNAME=root \
  -e PHD_TRACKER_DB_PASSWORD=password \
  phd-tracker
```

---

## 📚 API Documentation

Future enhancement: Integrate **Swagger/OpenAPI 3** for interactive API docs.

```xml
<!-- Add to pom.xml -->
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>2.2.0</version>
</dependency>
```

Access at: `http://localhost:8080/swagger-ui.html`

---

## 🔧 Troubleshooting

### Issue: Database Connection Failed

**Solution**: Verify MySQL is running and credentials are correct.

```bash
mysql -u root -p -e "SHOW DATABASES;"
```

### Issue: JWT Token Invalid

**Solution**: Ensure token hasn't expired (24-hour default) and `Authorization` header format is correct:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Issue: Access Denied (403)

**Solution**: Check user role matches endpoint requirements. Use correct role-based token.

---

## 📞 Support & Contact

- **Repository**: [https://github.com/vivekjindal24/phd-tracker](https://github.com/vivekjindal24/phd-tracker)
- **Issues**: [GitHub Issues](https://github.com/vivekjindal24/phd-tracker/issues)

---

## 📄 License

This project is for educational/thesis purposes. Modify as needed for your requirements.

---

## 🙏 Acknowledgments

Built with:
- Spring Boot Team
- Hibernate ORM
- JJWT Library
- MySQL Community

---

**Happy Coding! 🚀**

