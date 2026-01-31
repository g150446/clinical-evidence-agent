# Project: MedGemma Medical Evidence Search System

## Overview
Building a medical evidence search platform for Japanese hospitals using MedGemma AI. Participating in two hackathons with tight deadlines.

## Current Status
- **Phase**: Evidence Search MVP Development
- **Timeline**: 2 weeks until first hackathon (Feb 15, 2026)
- **Deployment**: Currently used at one hospital in Japan

## Hackathon Deadlines
1. **Japan Agentic AI Hackathon**: February 15, 2026 (Zenn article submission)
2. **MedGemma Impact Challenge**: February 24, 2026 (Kaggle writeup)

## Technical Architecture

### Core Components
```
User Query (Japanese/English)
    ↓
[Optional: Voice Input - Future Phase]
    ↓
PubMed/PMC API Search (Real-time)
    ↓
MedGemma Synthesis
    ↓
Evidence-Based Answer + Citations
```

### Technology Stack
- **AI Model**: MedGemma (google/medgemma-2b or larger)
- **Medical Database**: PubMed/PMC via NCBI E-utilities API (real-time)
- **Backend**: Python (FastAPI or Flask)
- **Frontend**: Simple React or HTML
- **Deployment**: Google Cloud Run or App Engine
- **Storage Strategy**: Real-time API + smart caching (hybrid approach)

### Data Strategy
- **NO bulk download** of papers for hackathon phase
- Use real-time PubMed API queries (3 requests/second limit)
- Simple in-memory caching for frequently searched papers
- Target: 5-10 papers per query for MedGemma context
- Post-hackathon: Build curated Japanese medical literature index (10K-50K papers)

## Implementation Priority

### Phase 1: Evidence Search MVP (NOW - Feb 10)
**Must Have:**
- PubMed API integration with basic caching
- MedGemma model integration for answer synthesis
- Simple web UI (text input → results display)
- Basic citation formatting
- Deploy to Google Cloud (Cloud Run preferred)

**Focus Areas:**
- Answer quality and relevance
- Fast response time (<10 seconds)
- Proper citation of sources
- Clean, professional UI

### Phase 2: Japan Hackathon Submission (Feb 11-15)
**Must Have:**
- "Agentic" framing (autonomous multi-step reasoning)
- Agent activity logs visible to user
- Demo video (3 minutes, Japanese)
- Zenn article (Japanese)
- Emphasis on autonomous evidence retrieval

**Agentic Features to Highlight:**
- Automatic query analysis
- Autonomous literature search
- Multi-source synthesis
- Decision-making without human intervention

### Phase 3: MedGemma Challenge (Feb 16-24) - IF TIME PERMITS
**Nice to Have:**
- MedASR fine-tuning for Japanese medical terms
- Enhanced documentation
- Better demo video
- Hugging Face model upload
- More comprehensive code comments

**If No Time:**
- Submit evidence search as-is
- Frame MedASR as "future work"
- Focus on evidence quality and impact

## Licensing Strategy

### Open Source Components (Apache 2.0)
- Evidence search core code (GitHub)
- API integration examples
- Basic UI components
- Documentation and tutorials

### Future Proprietary Components (Post-Hackathon)
- EHR system integrations
- Advanced compliance features
- Multi-hospital analytics dashboard
- Enterprise support tools

### Models
- MedGemma: Already open (Google's license)
- MedASR fine-tuned: Apache 2.0 if implemented
- Upload to Hugging Face with proper attribution

## Business Model (Post-Hackathon)

### Free Tier
- Open source code
- Self-hosted deployment
- Community support
- Basic documentation

### Paid Services
1. **Installation & Integration**: ¥500,000-1,500,000 per hospital
2. **Training Programs**: On-site clinician training
3. **Support Contracts**: ¥1,000,000-5,000,000/year (SLA guarantees)
4. **EHR Integrations**: Custom connectors for Epic, Cerner, etc.
5. **Compliance Documentation**: Regulatory approval support

## Key Success Metrics for Hackathons

### Japan Hackathon Judging Criteria
- **Problem novelty**: Japanese language barrier in medical evidence access
- **Solution effectiveness**: Autonomous evidence retrieval quality
- **Implementation quality**: Clean code, good UX, proper deployment

### MedGemma Challenge Judging Criteria
- **Effective use of HAI-DEF models** (20%): MedGemma integration quality
- **Problem domain** (15%): Healthcare impact and need
- **Impact potential** (15%): Scale of benefit to medical community
- **Product feasibility** (20%): Technical documentation and deployment
- **Execution and communication** (30%): Video, writeup, code quality

## Competitive Advantages
1. ✅ **Real hospital deployment** - Already in use (proof of concept)
2. ✅ **Japanese market focus** - Unique positioning for Japan
3. ✅ **Hybrid architecture** - Scalable from MVP to enterprise
4. ✅ **Open source foundation** - Community trust and contribution
5. ✅ **Both hackathons eligible** - Gemma family + Google Cloud deployment

## Important Constraints

### Technical Requirements
- **Japan Hackathon**: Must use Google Cloud deployment + Gemma family models
- **MedGemma Challenge**: Must use HAI-DEF models, CC BY 4.0 for submission docs
- Both require working demos and video presentations

### Timeline Constraints
- Only 2 weeks for MVP evidence search
- Cannot do bulk paper downloads (too slow)
- Must prioritize working demo over perfect features

### Agentic AI Requirements (Japan Hackathon)
- Must frame as "autonomous agent"
- Show multi-step reasoning
- Demonstrate decision-making capabilities
- Log agent activities for transparency

## Decision Context

### Why Evidence Search First?
- Core unique value proposition
- Works for both hackathons immediately  
- Can demo without voice input
- Proves concept for hospitals

### Why Real-time API vs Downloaded Papers?
- **Fast to implement** (1-2 days vs weeks)
- **Zero storage costs** for hackathon
- **Always up-to-date** papers
- **Full PubMed access** (37M abstracts)
- Can optimize later if needed

### Why Apache 2.0 Licensing?
- Patent protection (critical for medical software)
- Enterprise-friendly (hospitals prefer over GPL)
- Allows proprietary extensions
- Community contribution enabled
- Better than MIT for competitive protection

## Next Immediate Steps
1. Set up Python environment with MedGemma
2. Implement PubMed API integration
3. Create simple caching layer
4. Build basic web UI
5. Test end-to-end pipeline
6. Deploy to Google Cloud Run
7. Create demo scenarios

## Code Guidelines
- Keep MVP simple and focused
- Prioritize working demo over optimization
- Document agentic behavior clearly
- Use type hints and clear variable names
- Add logging for agent decision points
- Make code easy to understand for judges

## Communication Style for Submissions
- **Japan Hackathon**: Japanese language, emphasize local impact
- **Global Challenge**: English, emphasize technical innovation
- Both: Focus on real-world hospital use case
- Both: Highlight autonomous/agentic capabilities
- Both: Professional but accessible tone

## Resources & Links
- PubMed E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- MedGemma: https://developers.google.com/health-ai-developer-foundations
- Japan Hackathon: https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol4
- MedGemma Challenge: https://www.kaggle.com/competitions/med-gemma-impact-challenge

## Notes
- Hospital already using prototype - leverage this in presentations
- MedASR fine-tuning is Phase 2 (only if time permits)
- Focus on evidence quality over feature quantity
- Both hackathons allow same core project with different framing
