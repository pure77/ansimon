package com.nmdw.ansimon.support.infra;

import com.nmdw.ansimon.support.domain.SupportTask;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SupportTaskRepository extends JpaRepository<SupportTask, Long> {
}
