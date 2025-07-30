// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {A} from "./A.sol";
import {B} from "./B.sol";

contract C is A {
    using B for string;

    B.State public votes;
    uint256 b;
    function() internal c;

    constructor() {
        votes.name = "2024 Elections";
        name("meek");
    }

    function add_vote(string memory name) public returns (uint256) {
        name.add_one(votes);
        return name.get_votes(votes);
    }
}
