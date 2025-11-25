import asyncio
from backend.agents.base import AgentInterface

class MockAgent(AgentInterface):
    """Mock agent for development without real CLI tools"""

    def __init__(self, name: str, agent_type: str, role: str = "general", workspace_path: str = None):
        super().__init__(name, agent_type)
        self.role = role
        self.workspace_path = workspace_path

    async def start(self):
        await asyncio.sleep(0.5)  # Simulate startup
        self.status = "running"

    async def send_message(self, content: str, **kwargs) -> str:
        # Simulate processing time
        await asyncio.sleep(2)

        if self.role == "planning":
            return self._generate_plan_response(content)
        elif self.role == "review":
            return self._generate_review_response(content)
        else:
            return f"Mock response from {self.name} for: {content[:100]}..."

    async def get_status(self) -> dict:
        return {
            "name": self.name,
            "type": self.agent_type,
            "status": self.status,
            "role": self.role,
            "workspace_path": self.workspace_path
        }

    async def stop(self):
        self.status = "stopped"

    def _generate_plan_response(self, prompt: str) -> str:
        return f"""# Development Plan

## Overview
Based on the requirements provided, here's a comprehensive plan for implementation.

## Architecture
- **Backend**: Python FastAPI for REST API
- **Frontend**: React with TypeScript for UI
- **Database**: SQLite for initial development, PostgreSQL for production
- **Orchestration**: LangGraph for workflow management

## Implementation Steps

### Phase 1: Core Setup (Days 1-3)
1. Initialize project structure
2. Set up database schema
3. Create basic API endpoints
4. Implement authentication system

### Phase 2: Feature Development (Days 4-7)
1. Implement core business logic
2. Build user interface components
3. Add API integrations
4. Implement real-time updates

### Phase 3: Testing & Quality (Days 8-10)
1. Write comprehensive unit tests
2. Perform integration testing
3. Conduct security audit
4. Optimize performance

### Phase 4: Deployment (Days 11-12)
1. Set up CI/CD pipeline
2. Deploy to staging environment
3. User acceptance testing
4. Production deployment

## Technical Considerations

### Security
- Input validation and sanitization
- JWT-based authentication
- HTTPS/TLS encryption
- Rate limiting and DDoS protection
- SQL injection prevention

### Performance
- Database query optimization
- Caching strategy (Redis)
- API response compression
- Lazy loading for frontend
- Connection pooling

### Scalability
- Horizontal scaling capability
- Load balancing
- Database replication
- Microservices architecture consideration

## Timeline
- **Phase 1**: 3 days
- **Phase 2**: 4 days
- **Phase 3**: 3 days
- **Phase 4**: 2 days
- **Total**: 12 days (with 20% buffer = 14-15 days)

## Risks & Mitigation
1. **Risk**: Third-party API downtime
   - **Mitigation**: Implement retry logic and fallback mechanisms

2. **Risk**: Database scaling issues
   - **Mitigation**: Plan migration path to PostgreSQL early

3. **Risk**: Security vulnerabilities
   - **Mitigation**: Regular security audits and dependency updates
"""

    def _generate_review_response(self, prompt: str) -> str:
        return f"""# Review Feedback

## Overall Assessment
The plan is well-structured and comprehensive, demonstrating good understanding of modern web application architecture.

## Strengths ✅

### Architecture
- Good separation of concerns with FastAPI backend and React frontend
- Appropriate technology choices for the project scope
- Consideration of both development and production environments

### Planning
- Clear phasing with realistic time estimates
- Comprehensive coverage of security concerns
- Performance and scalability considerations included

### Risk Management
- Proactive identification of potential risks
- Concrete mitigation strategies provided

## Concerns & Recommendations 🔍

### 1. Database Strategy
**Issue**: SQLite to PostgreSQL migration can be complex and risky late in development.

**Recommendation**:
- Use PostgreSQL from the start with Docker for local development
- This avoids migration headaches and ensures development-production parity
- SQLite is fine for prototyping but plan mentions production use

### 2. Testing Phase Timing
**Issue**: Testing is placed after all development in Phase 3, which is risky.

**Recommendation**:
- Adopt Test-Driven Development (TDD) from Phase 1
- Write tests alongside features, not after
- Aim for 80%+ code coverage from the start
- Add integration tests in Phase 2, not Phase 3

### 3. Authentication Details
**Issue**: "Implement authentication system" lacks specifics.

**Recommendation**:
- Specify auth method: JWT, OAuth2, or session-based?
- Define user roles and permissions model
- Include password hashing strategy (bcrypt, argon2)
- Plan for password reset and email verification flows

### 4. Timeline Buffer
**Issue**: 20% buffer may be insufficient for unknowns.

**Recommendation**:
- Increase buffer to 30-40% for more realistic estimates
- Add explicit time for bug fixes and refactoring
- Include time for code reviews and documentation

### 5. Caching Strategy
**Issue**: Redis mentioned but not elaborated.

**Recommendation**:
- Define what specifically will be cached (sessions, API responses, etc.)
- Specify cache invalidation strategy
- Consider if Redis is truly needed initially or if in-memory caching suffices

### 6. API Documentation
**Issue**: No mention of API documentation strategy.

**Recommendation**:
- Use FastAPI's built-in OpenAPI/Swagger generation
- Add comprehensive docstrings to all endpoints
- Include example requests/responses
- Create API versioning strategy (v1, v2, etc.)

## Priority Action Items 🔴

1. **CRITICAL**: Choose authentication method and document the auth flow
2. **CRITICAL**: Decide on PostgreSQL vs SQLite for development
3. **HIGH**: Move testing earlier in the timeline (parallel to development)
4. **HIGH**: Add API documentation to Phase 1 tasks
5. **MEDIUM**: Increase timeline buffer to 30-40%
6. **MEDIUM**: Elaborate on caching strategy details

## Questions for Clarification ❓

1. What is the expected user load? (affects scaling decisions)
2. Are there specific compliance requirements (GDPR, HIPAA, etc.)?
3. Will this integrate with existing systems?
4. What monitoring and observability tools will be used?

## Conclusion
This is a solid foundation for a plan. Addressing the concerns above will significantly reduce risk and improve the chances of successful delivery on time and within budget.

**Recommendation**: Revise and resubmit after addressing critical items.
"""
