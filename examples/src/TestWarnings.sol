// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract TestWarnings {
    uint256 public value;
    uint256 private unusedVar; // This should generate a warning

    function setValue(uint256 _value) public {
        value = _value;
    }

    function getValue() public view returns (uint256) {
        return value;
    }
}
