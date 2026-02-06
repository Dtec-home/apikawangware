Feature: Manual Contribution Entry
  As a church administrator
  I want to manually enter cash and envelope contributions
  So that all contributions are tracked in the system

  Background:
    Given I am logged in as an administrator
    And the following contribution categories exist:
      | name         | code    | is_active |
      | Tithe        | TITHE   | true      |
      | Building Fund| BUILD   | true      |

  Scenario: Manual entry for existing member
    Given a member exists with phone "254712345678"
    When I manually enter a contribution:
      | phone_number  | 254712345678 |
      | amount        | 5000         |
      | category      | Tithe        |
      | entry_type    | cash         |
      | receipt_number| CASH-001     |
    Then the contribution should be recorded as "completed"
    And the member should receive an SMS receipt
    And the contribution should be linked to the existing member

  Scenario: Manual entry creates guest member
    Given no member exists with phone "254798765432"
    When I manually enter a contribution:
      | phone_number  | 254798765432 |
      | amount        | 2000         |
      | category      | Building Fund|
      | entry_type    | envelope     |
    Then a guest member should be created
    And the contribution should be recorded as "completed"
    And the guest member should receive an SMS receipt

  Scenario: Manual entry with auto-generated receipt number
    When I manually enter a contribution without a receipt number:
      | phone_number  | 254712345678 |
      | amount        | 1000         |
      | category      | Tithe        |
      | entry_type    | manual       |
    Then a receipt number should be auto-generated
    And the receipt number should start with "MAN-"

  Scenario: Manual entry with custom transaction date
    When I manually enter a contribution with date "2026-01-15":
      | phone_number  | 254712345678 |
      | amount        | 3000         |
      | category      | Tithe        |
      | entry_type    | cash         |
    Then the contribution transaction date should be "2026-01-15"

  Scenario: Invalid manual entry - amount too low
    When I try to manually enter a contribution:
      | phone_number  | 254712345678 |
      | amount        | 0.50         |
      | category      | Tithe        |
      | entry_type    | cash         |
    Then I should receive an error about minimum amount
    And no contribution should be created

  Scenario: Invalid manual entry - inactive category
    Given the "Tithe" category is inactive
    When I try to manually enter a contribution to "Tithe"
    Then I should receive an error about inactive category
    And no contribution should be created
