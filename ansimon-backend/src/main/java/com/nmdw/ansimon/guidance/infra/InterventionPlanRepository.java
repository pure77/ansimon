package com.nmdw.ansimon.guidance.infra;

import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import org.springframework.data.jpa.repository.JpaRepository;

public interface InterventionPlanRepository extends JpaRepository<InterventionPlan, Long> {
}
