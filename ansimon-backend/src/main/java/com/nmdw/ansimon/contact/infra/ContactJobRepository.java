package com.nmdw.ansimon.contact.infra;

import com.nmdw.ansimon.contact.domain.ContactJob;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ContactJobRepository extends JpaRepository<ContactJob, Long> {

    boolean existsByIdempotencyKey(String idempotencyKey);
}
