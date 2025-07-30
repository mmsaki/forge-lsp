// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {C} from "../src/C.sol";

contract CTest is Test {
    C public c;

    function setUp() public {
        c = new C();
    }
}
